"""Module D (Part 1): Site-Ranking and Catchment Evaluation (PS000002).

Audited and hardened implementation (Task 4b):
- Regular 500 m candidate grid strictly bounded to municipal urban extents (SMC and RUDA).
- Land mask: Excludes water/sea cells and requires raster density >= 1000 persons/km2
  in the candidate cell AND in at least 5 of its 8 neighbouring cells.
- Exclusion zones: Uses ALL known stations for exclusion:
    * Reliable stations (high/medium confidence, unique coords): exclude within d_min.
    * Approximate stations (low-confidence, pincode centroids, duplicates): exclude
      within d_min + 1.5 km to allow for geocoding locational error.
- Reliable stations used exclusively for overlap and unserved-population calculations.
- Implied density reported alongside unserved population.
- 5-seed leave-out sanity test with transparent reporting.

STRICT CONSTRAINTS:
- No invented observed data.
- All modeling assumptions explicitly tagged with ASSUMPTION.
- Scores are relative priority scores, not sales forecasts.
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Global Coordinate Reference Systems
PROJ_CRS = "EPSG:32643"  # UTM Zone 43N (metric)
WGS84_CRS = "EPSG:4326"   # Geographic latitude/longitude

# Municipal Urban Extents (lon_min, lat_min, lon_max, lat_max)
# Derived from Surat Municipal Corporation (SMC) and Rajkot Urban Development Authority (RUDA) urban limits
MUNICIPAL_BOUNDS = {
    "Surat": (72.74, 21.08, 72.93, 21.28),   # SMC urban agglomeration (excludes coastal marshes/Hazira port)
    "Rajkot": (70.65, 22.15, 70.90, 22.42)   # RUDA urban agglomeration along radial transport corridors
}

# City Centroids
CITY_CENTRES = {
    "Surat": (21.1702, 72.8311),
    "Rajkot": (22.3039, 70.8022)
}

# Spacing Parameters from spacing_summary.csv (20% overlap threshold)
DEFAULT_MIN_SPACING_KM = {
    "Surat": 3.11,
    "Rajkot": 3.07
}

# Buffer Parameters (ASSUMPTION tags)
DEFAULT_CATCHMENT_RADIUS_M = 2000.0   # ASSUMPTION: 2.0 km circular buffer proxy for 5-min driving catchment
DEFAULT_POP_THRESHOLD = 1000.0        # ASSUMPTION: MoHUA urban agglomeration density threshold
DEFAULT_APPROX_BUFFER_KM = 1.5        # ASSUMPTION: Location error margin for approximate geocodes
DEFAULT_W_UNSERVED = 1.0              # ASSUMPTION: Weight on unserved population share
DEFAULT_W_OVERLAP = 0.5               # ASSUMPTION: Penalty coefficient on nearest station overlap
LEAVE_OUT_SEEDS = [42, 101, 777, 2023, 9999]


def load_and_classify_stations(stations_path="data/processed/stations_geocoded.csv"):
    """Load all geocoded stations and classify into reliable vs approximate stations.

    - Reliable stations: confidence in ['high', 'medium'] AND unique coordinates.
    - Approximate stations: confidence in ['low', 'none'] OR shared coordinates (pincode centroids).
    """
    if not os.path.exists(stations_path):
        raise FileNotFoundError(f"Stations file not found: {stations_path}")

    df = pd.read_csv(stations_path)
    geocoded_df = df[df["geocoded"] == True].copy().reset_index(drop=True)

    pt_counts = geocoded_df.groupby(["lat", "lon"]).size()
    dup_coords = pt_counts[pt_counts > 1].index

    reliable = geocoded_df[
        geocoded_df["confidence"].isin(["high", "medium"])
        & (~geocoded_df.set_index(["lat", "lon"]).index.isin(dup_coords))
    ].copy().reset_index(drop=True)

    approx = geocoded_df[~geocoded_df.index.isin(reliable.index)].copy().reset_index(drop=True)

    return reliable, approx


def build_municipal_candidate_grid(
    city,
    gdf_reliable,
    gdf_approx,
    city_raster,
    win_trans,
    min_spacing_km,
    approx_buffer_km=1.5,
    pop_threshold=1000.0,
    step_m=500.0
):
    """Generate candidate grid within municipal bounds and enforce land mask + exclusion zones."""
    min_lon, min_lat, max_lon, max_lat = MUNICIPAL_BOUNDS[city]
    b_poly = gpd.GeoSeries([Point(min_lon, min_lat), Point(max_lon, max_lat)], crs=WGS84_CRS).to_crs(PROJ_CRS)
    ux_min, uy_min = b_poly.iloc[0].x, b_poly.iloc[0].y
    ux_max, uy_max = b_poly.iloc[1].x, b_poly.iloc[1].y

    xs = np.arange(min(ux_min, ux_max), max(ux_min, ux_max) + step_m, step_m)
    ys = np.arange(min(uy_min, uy_max), max(uy_min, uy_max) + step_m, step_m)
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    grid_pts = [Point(x, y) for x, y in zip(mesh_x.flatten(), mesh_y.flatten())]
    gdf_grid = gpd.GeoDataFrame(geometry=grid_pts, crs=PROJ_CRS)
    n_total_grid = len(gdf_grid)

    # Sample raster population
    gdf_grid_wgs = gdf_grid.to_crs(WGS84_CRS)
    inv_trans = ~win_trans
    sampled_vals = []
    for p in gdf_grid_wgs.geometry:
        col, row = inv_trans * (p.x, p.y)
        col, row = int(round(col)), int(round(row))
        if 0 <= row < city_raster.shape[0] and 0 <= col < city_raster.shape[1]:
            val = float(city_raster[row, col])
            sampled_vals.append(max(0.0, val))
        else:
            sampled_vals.append(0.0)

    sampled_vals = np.array(sampled_vals)
    grid_shape = mesh_x.shape
    val_grid = sampled_vals.reshape(grid_shape)

    # Land mask: center >= pop_threshold AND at least 5 of 8 neighbors >= pop_threshold
    built_mask = np.zeros(grid_shape, dtype=bool)
    rows, cols = grid_shape
    for r in range(rows):
        for c in range(cols):
            if val_grid[r, c] >= pop_threshold:
                n_count = 0
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            if val_grid[nr, nc] >= pop_threshold:
                                n_count += 1
                if n_count >= 5:
                    built_mask[r, c] = True

    gdf_grid["is_built"] = built_mask.flatten()
    gdf_grid["pop_density"] = sampled_vals
    built_cand = gdf_grid[gdf_grid["is_built"]].copy().reset_index(drop=True)
    n_built = len(built_cand)

    # Exclusion zones
    d_app_thresh = min_spacing_km + approx_buffer_km
    ex_rel = []
    ex_app = []
    near_rel_dists = []
    near_rel_idx = []

    for i in range(len(built_cand)):
        p = built_cand.geometry.iloc[i]
        d_rel_all = [p.distance(st) / 1000.0 for st in gdf_reliable.geometry]
        d_r = min(d_rel_all)
        idx_r = np.argmin(d_rel_all)
        near_rel_dists.append(d_r)
        near_rel_idx.append(idx_r)

        d_a = min([p.distance(st) / 1000.0 for st in gdf_approx.geometry]) if not gdf_approx.empty else 999.0
        ex_rel.append(d_r < min_spacing_km)
        ex_app.append(d_a < d_app_thresh)

    built_cand["nearest_station_km"] = near_rel_dists
    built_cand["nearest_st_idx"] = near_rel_idx
    built_cand["ex_rel"] = ex_rel
    built_cand["ex_app"] = ex_app

    removed_rel = sum(ex_rel)
    removed_app_only = sum(built_cand["ex_app"] & (~built_cand["ex_rel"]))
    total_excluded = sum(built_cand["ex_rel"] | built_cand["ex_app"])
    eligible = built_cand[~(built_cand["ex_rel"] | built_cand["ex_app"])].copy().reset_index(drop=True)

    audit_stats = {
        "n_total_grid": n_total_grid,
        "n_built": n_built,
        "removed_rel": removed_rel,
        "removed_app_only": removed_app_only,
        "total_excluded": total_excluded,
        "n_eligible": len(eligible)
    }

    return eligible, audit_stats


def compute_geometry_pop(geom_4326, city_raster, win_trans):
    """Compute aggregate population inside a WGS84 polygon using the cropped raster window."""
    if geom_4326.is_empty:
        return 0.0
    mask = geometry_mask([geom_4326], out_shape=city_raster.shape, transform=win_trans, invert=True)
    return float(np.sum(city_raster[mask]))


def score_candidate_sites(
    eligible,
    gdf_reliable,
    city_raster,
    win_trans,
    catchment_radius_m=2000.0,
    w_unserved=1.0,
    w_overlap=0.5
):
    """Compute unserved population, overlap penalty, implied density, and rank sites."""
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()

    st_bufs_m = gdf_reliable.geometry.buffer(catchment_radius_m)
    union_existing_m = unary_union(st_bufs_m)

    st_bufs_4326 = gpd.GeoSeries(st_bufs_m, crs=PROJ_CRS).to_crs(WGS84_CRS)
    st_demands = [compute_geometry_pop(b, city_raster, win_trans) for b in st_bufs_4326]

    cand_bufs_m = eligible.geometry.buffer(catchment_radius_m)
    cand_bufs_4326 = gpd.GeoSeries(cand_bufs_m, crs=PROJ_CRS).to_crs(WGS84_CRS)

    c_pop = []
    u_pop = []
    ov_shares = []

    for i in range(len(eligible)):
        b_c_m = cand_bufs_m.iloc[i]
        b_c_4326 = cand_bufs_4326.iloc[i]

        pop_total = compute_geometry_pop(b_c_4326, city_raster, win_trans)
        c_pop.append(pop_total)

        geom_unserved_m = b_c_m.difference(union_existing_m)
        if geom_unserved_m.is_empty:
            pop_unserved = 0.0
        else:
            geom_u_4326 = gpd.GeoSeries([geom_unserved_m], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
            pop_unserved = compute_geometry_pop(geom_u_4326, city_raster, win_trans)
        u_pop.append(pop_unserved)

        nst_i = eligible.loc[i, "nearest_st_idx"]
        d_km = eligible.loc[i, "nearest_station_km"]
        ov_s = 0.0
        if d_km < (2.0 * catchment_radius_m / 1000.0):
            inter_m = b_c_m.intersection(st_bufs_m.iloc[nst_i])
            if not inter_m.is_empty:
                inter_4326 = gpd.GeoSeries([inter_m], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
                pop_inter = compute_geometry_pop(inter_4326, city_raster, win_trans)
                min_d = min(pop_total, st_demands[nst_i])
                ov_s = min(1.0, pop_inter / min_d if min_d > 0 else 0.0)
        ov_shares.append(ov_s)

    eligible["catchment_pop"] = c_pop
    eligible["unserved_pop"] = u_pop
    eligible["unserved_share"] = eligible["unserved_pop"] / eligible["catchment_pop"].replace(0, 1)
    eligible["overlap_share"] = ov_shares

    # Implied density (people per km2 of 2km circular buffer = 12.566 km2)
    buf_area_km2 = np.pi * ((catchment_radius_m / 1000.0) ** 2)
    eligible["implied_density"] = eligible["catchment_pop"] / buf_area_km2

    max_unserved = max(1.0, eligible["unserved_pop"].max())
    eligible["score"] = (
        w_unserved * eligible["unserved_share"] * (eligible["unserved_pop"] / max_unserved)
        - w_overlap * eligible["overlap_share"]
    ) * 100.0

    eligible_wgs = eligible.to_crs(WGS84_CRS)
    eligible["lat"] = eligible_wgs.geometry.y
    eligible["lon"] = eligible_wgs.geometry.x

    all_ranked = eligible.sort_values("score", ascending=False).reset_index(drop=True)
    all_ranked["rank"] = range(1, len(all_ranked) + 1)
    top10 = all_ranked.head(10).copy()

    return all_ranked, top10


def run_5seed_leave_out_test(city, gdf_reliable, gdf_approx, city_raster, win_trans, min_spacing_km, catchment_radius_m=2000.0):
    """Sanity check: remove 20% of reliable stations across 5 random seeds and test recovery."""
    n_st = len(gdf_reliable)
    n_leave = max(1, int(round(0.20 * n_st)))

    seed_results = []
    for seed in LEAVE_OUT_SEEDS:
        rng = np.random.default_rng(seed)
        leave_indices = rng.choice(n_st, size=n_leave, replace=False)

        gdf_retained = gdf_reliable.drop(index=leave_indices).reset_index(drop=True)
        gdf_removed = gdf_reliable.iloc[leave_indices].reset_index(drop=True)

        eligible, _ = build_municipal_candidate_grid(
            city,
            gdf_retained,
            gdf_approx,
            city_raster,
            win_trans,
            min_spacing_km=min_spacing_km,
            pop_threshold=DEFAULT_POP_THRESHOLD
        )
        _, top10_recomputed = score_candidate_sites(
            eligible,
            gdf_retained,
            city_raster,
            win_trans,
            catchment_radius_m=catchment_radius_m
        )

        recovered_count = 0
        details = []
        for _, r_st in gdf_removed.iterrows():
            cand_dists = [r_st.geometry.distance(c.geometry) / 1000.0 for _, c in top10_recomputed.iterrows()]
            min_dist = min(cand_dists) if cand_dists else 999.0
            is_recovered = min_dist <= (catchment_radius_m / 1000.0)
            if is_recovered:
                recovered_count += 1
            details.append({
                "removed_station": r_st.get("station_name", "Unknown"),
                "closest_candidate_km": round(min_dist, 2),
                "recovered": is_recovered
            })

        recovery_rate = (recovered_count / n_leave) * 100.0
        seed_results.append({
            "seed": seed,
            "n_removed": n_leave,
            "recovered_count": recovered_count,
            "recovery_rate_pct": recovery_rate,
            "details": details
        })

    mean_recovery = float(np.mean([sr["recovery_rate_pct"] for sr in seed_results]))
    return {
        "city": city,
        "n_stations": n_st,
        "n_removed_per_seed": n_leave,
        "mean_recovery_pct": mean_recovery,
        "seed_results": seed_results
    }


def plot_ranked_sites_map(city, gdf_reliable, gdf_approx, top10, city_raster, win_trans, output_png_path, catchment_radius_m=2000.0):
    """Cartographic map of top candidate sites and exclusion network over population density."""
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)

    h, w = city_raster.shape
    top_left = win_trans * (0, 0)
    bot_right = win_trans * (w, h)
    extent = [top_left[0], bot_right[0], bot_right[1], top_left[1]]

    plot_raster = np.log1p(city_raster)
    im = ax.imshow(plot_raster, extent=extent, cmap="YlOrRd", alpha=0.55, origin="upper")
    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("Population Density (log scale, persons/km²)", fontsize=9, fontweight="bold")

    # Plot approximate stations and error buffers
    if not gdf_approx.empty:
        gdf_app_wgs = gdf_approx.to_crs(WGS84_CRS)
        ax.scatter(gdf_app_wgs.geometry.x, gdf_app_wgs.geometry.y, color="#7f7f7f", s=30, marker="^", alpha=0.7, label=f"Approximate/Pincode Stations (N={len(gdf_approx)})")

    # Plot reliable stations and buffer catchments
    gdf_rel_wgs = gdf_reliable.to_crs(WGS84_CRS)
    st_bufs_4326 = gpd.GeoSeries(gdf_reliable.geometry.buffer(catchment_radius_m), crs=PROJ_CRS).to_crs(WGS84_CRS)
    st_bufs_4326.plot(ax=ax, facecolor="none", edgecolor="#1f77b4", linewidth=1.2, linestyle="--", label="Reliable Station Catchment (2.0 km)")
    ax.scatter(gdf_rel_wgs.geometry.x, gdf_rel_wgs.geometry.y, color="#1f77b4", s=50, marker="s", edgecolors="black", linewidth=0.8, zorder=4, label=f"Reliable Stations (N={len(gdf_reliable)})")

    # Plot top candidate sites
    top10_wgs = gpd.GeoDataFrame(top10, geometry=[Point(xy) for xy in zip(top10["lon"], top10["lat"])], crs=WGS84_CRS)
    cand_bufs_4326 = gpd.GeoSeries(top10["geometry"].values, crs=PROJ_CRS).buffer(catchment_radius_m).to_crs(WGS84_CRS)
    cand_bufs_4326.plot(ax=ax, facecolor="#2ca02c", alpha=0.15, edgecolor="#2ca02c", linewidth=1.5, linestyle="-", label="Candidate Catchment (2.0 km)")

    ax.scatter(top10_wgs.geometry.x, top10_wgs.geometry.y, c=top10["score"], cmap="viridis", s=180, marker="*", edgecolors="black", linewidth=1.0, zorder=5, label=f"Top {len(top10)} Candidate Sites")

    for _, row in top10.iterrows():
        ax.annotate(
            f"#{int(row['rank'])}",
            (row["lon"], row["lat"]),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#2ca02c", alpha=0.85),
            zorder=6
        )

    # City center
    clat, clon = CITY_CENTRES[city]
    ax.scatter([clon], [clat], color="black", marker="x", s=80, linewidth=2, zorder=4, label="City Center")

    min_lon, min_lat, max_lon, max_lat = MUNICIPAL_BOUNDS[city]
    ax.set_xlim(min_lon - 0.01, max_lon + 0.01)
    ax.set_ylim(min_lat - 0.01, max_lat + 0.01)

    ax.set_title(
        f"{city}: Top Ranked Candidate Siting Opportunities\n"
        f"(Municipal Urban Extent | 20% Overlap Spacing: {DEFAULT_MIN_SPACING_KM[city]} km | Catchment: {catchment_radius_m/1000.0:.1f} km [ASSUMPTION])",
        fontsize=11,
        fontweight="bold",
        pad=10
    )
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.92)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path, dpi=300)
    plt.close()
    print(f"  [Figure] Saved audited map to {output_png_path}")


def main():
    parser = argparse.ArgumentParser(description="Audited site-ranking module (PS000002 Module D Part 1).")
    parser.add_argument("--stations-file", default="data/processed/stations_geocoded.csv", help="Clean geocoded stations path")
    parser.add_argument("--raster-file", default="data/raw/ind_ppp_2020_1km_UNadj.tif", help="WorldPop raster path")
    parser.add_argument("--output-csv", default="data/processed/ranked_sites.csv", help="Output path for ranked sites CSV")
    parser.add_argument("--output-fig-dir", default="outputs/figures", help="Output directory for map figures")
    args = parser.parse_args()

    print("=" * 80)
    print("MODULE D: AUDITED SITE-RANKING & BUFFER CATCHMENT EVALUATION (PART 1)")
    print("=" * 80)
    print("STRICT GUIDELINE VERIFICATION:")
    print("  - Search box: Bounded to municipal urban extents (SMC & RUDA).")
    print("  - Land check: Center cell >= 1000 pop/km2 AND >= 5 of 8 neighbors >= 1000 pop/km2.")
    print("  - Exclusion zones: Reliable stations (d < d_min) + Approximate stations (d < d_min + 1.5 km).")
    print("  - Overlap/Unserved pop: Calculated strictly against verified reliable stations.")
    print("=" * 80)

    reliable_all, approx_all = load_and_classify_stations(args.stations_file)
    print(f"Total geocoded stations loaded: {len(reliable_all) + len(approx_all)}")
    print(f"  Reliable operating stations: {len(reliable_all)}")
    print(f"  Approximate / pincode stations: {len(approx_all)}")

    all_top10 = []
    leave_out_summary = []

    for city in ["Surat", "Rajkot"]:
        print(f"\nProcessing {city.upper()}...")
        st_rel = reliable_all[reliable_all["city"] == city].copy().reset_index(drop=True)
        st_app = approx_all[approx_all["city"] == city].copy().reset_index(drop=True)

        gdf_rel = gpd.GeoDataFrame(st_rel, geometry=[Point(lo, la) for lo, la in zip(st_rel["lon"], st_rel["lat"])], crs=WGS84_CRS).to_crs(PROJ_CRS)
        gdf_app = gpd.GeoDataFrame(st_app, geometry=[Point(lo, la) for lo, la in zip(st_app["lon"], st_app["lat"])], crs=WGS84_CRS).to_crs(PROJ_CRS)

        print(f"  Reliable stations: {len(gdf_rel)} | Approximate stations: {len(gdf_app)}")

        min_spacing_km = DEFAULT_MIN_SPACING_KM[city]
        print(f"  Spacing parameter: {min_spacing_km:.2f} km (reliable) | {min_spacing_km + DEFAULT_APPROX_BUFFER_KM:.2f} km (approximate)")

        # Load raster window
        min_lon, min_lat, max_lon, max_lat = MUNICIPAL_BOUNDS[city]
        pad = 0.05
        with rasterio.open(args.raster_file) as src:
            win = from_bounds(min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad, src.transform)
            city_raster = src.read(1, window=win)
            win_trans = src.window_transform(win)
            city_raster = np.where(city_raster < 0, 0.0, city_raster)
            city_raster = np.nan_to_num(city_raster, nan=0.0)

        # Build candidate grid
        eligible, stats = build_municipal_candidate_grid(
            city,
            gdf_rel,
            gdf_app,
            city_raster,
            win_trans,
            min_spacing_km=min_spacing_km,
            pop_threshold=DEFAULT_POP_THRESHOLD
        )

        print(f"  Municipal grid cells: {stats['n_total_grid']} total | {stats['n_built']} built-up (>=5/8 neighbors)")
        print(f"  Exclusion breakdown: {stats['removed_rel']} excluded by reliable stations | {stats['removed_app_only']} additional excluded by approximate stations")
        print(f"  Total cells excluded: {stats['total_excluded']} ({(stats['total_excluded']/stats['n_built'])*100:.1f}%) | Eligible candidate cells: {stats['n_eligible']}")

        # Score candidates
        all_ranked, top10 = score_candidate_sites(
            eligible,
            gdf_rel,
            city_raster,
            win_trans,
            catchment_radius_m=DEFAULT_CATCHMENT_RADIUS_M,
            w_unserved=DEFAULT_W_UNSERVED,
            w_overlap=DEFAULT_W_OVERLAP
        )

        top10["city"] = city
        all_top10.append(top10)

        print(f"\n  Top Ranked Candidate Siting Opportunities in {city}:")
        cols_show = ["rank", "lat", "lon", "unserved_pop", "catchment_pop", "implied_density", "nearest_station_km", "score"]
        print(top10[cols_show].to_string(index=False))

        # Plot map
        fig_path = os.path.join(args.output_fig_dir, f"ranked_sites_{city.lower()}.png")
        plot_ranked_sites_map(city, gdf_rel, gdf_app, top10, city_raster, win_trans, fig_path, DEFAULT_CATCHMENT_RADIUS_M)

        # 5-Seed Leave-Out Test
        print(f"\n  Running 5-Seed Leave-Out Sanity Test for {city} (Seeds: {LEAVE_OUT_SEEDS})...")
        lo_report = run_5seed_leave_out_test(city, gdf_rel, gdf_app, city_raster, win_trans, min_spacing_km)
        leave_out_summary.append(lo_report)
        print(f"  Mean Recovery across 5 seeds: {lo_report['mean_recovery_pct']:.1f}%")
        for sr in lo_report["seed_results"]:
            print(f"    - Seed {sr['seed']}: {sr['recovered_count']}/{sr['n_removed']} recovered ({sr['recovery_rate_pct']:.1f}%)")

    # Combine and save CSV
    if all_top10:
        df_out = pd.concat(all_top10, ignore_index=True)
        cols_save = [
            "city", "rank", "lat", "lon", "unserved_pop", "catchment_pop",
            "implied_density", "pop_density", "unserved_share", "overlap_share",
            "nearest_station_km", "score"
        ]
        df_final = df_out[cols_save].copy()
        df_final["lat"] = df_final["lat"].round(6)
        df_final["lon"] = df_final["lon"].round(6)
        df_final["unserved_pop"] = df_final["unserved_pop"].round(1)
        df_final["catchment_pop"] = df_final["catchment_pop"].round(1)
        df_final["implied_density"] = df_final["implied_density"].round(1)
        df_final["pop_density"] = df_final["pop_density"].round(1)
        df_final["unserved_share"] = df_final["unserved_share"].round(4)
        df_final["overlap_share"] = df_final["overlap_share"].round(4)
        df_final["nearest_station_km"] = df_final["nearest_station_km"].round(3)
        df_final["score"] = df_final["score"].round(2)

        os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
        df_final.to_csv(args.output_csv, index=False)
        print("\n" + "=" * 80)
        print(f"SUCCESS: Corrected ranked candidate sites saved to {args.output_csv}")
        print("=" * 80)


if __name__ == "__main__":
    main()
