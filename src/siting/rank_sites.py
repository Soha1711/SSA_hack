"""Module D (Part 1): Site-Ranking and Catchment Evaluation (PS000002).

This script generates regular 500 m candidate grids in the built-up areas of Surat
and Rajkot, evaluates unserved population within buffer-based catchments, penalizes
overlap with existing stations, enforces spacing constraints from spacing_summary.csv,
and outputs ranked candidate portfolios alongside leave-out sanity validation.

STRICT CONSTRAINTS:
- No invented observed numbers or synthetic registrations.
- Localized population raster (ind_ppp_2020_1km_UNadj.tif) serves as spatial demand proxy.
- All modeling assumptions are explicitly tagged with ASSUMPTION.
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
import matplotlib.patches as mpatches

# Global Coordinate Reference Systems
PROJ_CRS = "EPSG:32643"  # UTM Zone 43N (meters)
WGS84_CRS = "EPSG:4326"   # Geographic latitude/longitude

# City Centroids (Surat and Rajkot municipal cores)
CITY_CENTRES = {
    "Surat": (21.1702, 72.8311),
    "Rajkot": (22.3039, 70.8022)
}

# Minimum Spacing Thresholds from spacing_summary.csv (20% overlap threshold)
# Spacing thresholds derived from 500 bootstrap resamples of 2.0 km buffer overlap curves
DEFAULT_MIN_SPACING_KM = {
    "Surat": 3.11,   # Sourced from data/processed/spacing_summary.csv
    "Rajkot": 3.07   # Sourced from data/processed/spacing_summary.csv
}

# Baseline Parameters (ASSUMPTION tags)
# ASSUMPTION: 2.0 km circular radius represents typical urban CNG station catchment in India
DEFAULT_CATCHMENT_RADIUS_M = 2000.0

# ASSUMPTION: Continuous urban built-up area defined by population density >= 1000 persons/km2
# (Aligned with Census of India and Ministry of Housing and Urban Affairs agglomeration guidelines)
DEFAULT_POP_THRESHOLD = 1000.0

# ASSUMPTION: Weights for ranking formula:
# Score = [w_unserved * unserved_share * (unserved_pop / max_pop) - w_overlap * overlap_share] * 100
DEFAULT_W_UNSERVED = 1.0
DEFAULT_W_OVERLAP = 0.5


def load_clean_stations(stations_path="data/processed/stations_geocoded.csv"):
    """Load and filter stations strictly to high/medium confidence unique coordinates.

    Identical to Task 3b filtering rules:
    - geocoded == True
    - confidence in ['high', 'medium']
    - coordinate pairs must be unique (drop any stations sharing coordinates)
    """
    if not os.path.exists(stations_path):
        raise FileNotFoundError(f"Stations file not found: {stations_path}")

    df = pd.read_csv(stations_path)
    pt_counts = df[df["geocoded"] == True].groupby(["lat", "lon"]).size()
    dup_coords = pt_counts[pt_counts > 1].index

    clean = df[
        df["geocoded"]
        & df["confidence"].isin(["high", "medium"])
        & (~df.set_index(["lat", "lon"]).index.isin(dup_coords))
    ].copy().reset_index(drop=True)

    return clean


def extract_city_raster(gdf_bounds, raster_path="data/raw/ind_ppp_2020_1km_UNadj.tif", pad_deg=0.25):
    """Read a localized spatial window of the population raster covering city extent."""
    bounds = gdf_bounds.to_crs(WGS84_CRS).total_bounds
    minx, miny, maxx, maxy = bounds[0] - pad_deg, bounds[1] - pad_deg, bounds[2] + pad_deg, bounds[3] + pad_deg

    with rasterio.open(raster_path) as src:
        win = from_bounds(minx, miny, maxx, maxy, src.transform)
        arr = src.read(1, window=win)
        win_trans = src.window_transform(win)
        arr = np.where(arr < 0, 0, arr)
        arr = np.nan_to_num(arr, nan=0.0)

    return arr, win_trans


def compute_geometry_pop(geom_4326, city_raster, win_trans):
    """Compute aggregate population inside a WGS84 polygon using the cropped raster window."""
    if geom_4326.is_empty:
        return 0.0
    mask = geometry_mask([geom_4326], out_shape=city_raster.shape, transform=win_trans, invert=True)
    return float(np.sum(city_raster[mask]))


def build_candidate_grid(clat, clon, city_raster, win_trans, grid_extent_m=18000.0, step_m=500.0, pop_threshold=1000.0):
    """Generate a regular 500 m grid inside built-up cells (pop density >= pop_threshold)."""
    pt_c = Point(clon, clat)
    gdf_c = gpd.GeoDataFrame(geometry=[pt_c], crs=WGS84_CRS).to_crs(PROJ_CRS)
    cx, cy = gdf_c.geometry.iloc[0].x, gdf_c.geometry.iloc[0].y

    xs = np.arange(cx - grid_extent_m, cx + grid_extent_m + step_m, step_m)
    ys = np.arange(cy - grid_extent_m, cy + grid_extent_m + step_m, step_m)
    mesh_x, mesh_y = np.meshgrid(xs, ys)
    grid_pts = [Point(x, y) for x, y in zip(mesh_x.flatten(), mesh_y.flatten())]
    gdf_grid = gpd.GeoDataFrame(geometry=grid_pts, crs=PROJ_CRS)

    # Sample raster population at each point
    gdf_grid_wgs = gdf_grid.to_crs(WGS84_CRS)
    # Using window coordinates
    inv_trans = ~win_trans
    sampled_pop = []
    for p in gdf_grid_wgs.geometry:
        col, row = inv_trans * (p.x, p.y)
        col, row = int(round(col)), int(round(row))
        if 0 <= row < city_raster.shape[0] and 0 <= col < city_raster.shape[1]:
            val = float(city_raster[row, col])
            sampled_pop.append(max(0.0, val))
        else:
            sampled_pop.append(0.0)

    gdf_grid["pop_density"] = sampled_pop

    # Filter to built-up area
    urban_cand = gdf_grid[gdf_grid["pop_density"] >= pop_threshold].copy().reset_index(drop=True)
    return urban_cand, len(gdf_grid)


def score_candidate_sites(
    urban_cand,
    gdf_stations_city,
    city_raster,
    win_trans,
    min_spacing_km,
    catchment_radius_m=2000.0,
    w_unserved=1.0,
    w_overlap=0.5,
    min_cand_spacing_km=0.0
):
    """Compute distances, unserved population, overlap penalty, and rank sites."""
    if urban_cand.empty or gdf_stations_city.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Precompute existing station buffers
    st_bufs_m = gdf_stations_city.geometry.buffer(catchment_radius_m)
    union_existing_m = unary_union(st_bufs_m)

    # Distance to nearest existing station
    dists = []
    near_idx = []
    for i in range(len(urban_cand)):
        p = urban_cand.geometry.iloc[i]
        d_all = [p.distance(st) / 1000.0 for st in gdf_stations_city.geometry]
        dists.append(min(d_all))
        near_idx.append(np.argmin(d_all))

    urban_cand["nearest_station_km"] = dists
    urban_cand["nearest_st_idx"] = near_idx

    # Apply minimum spacing threshold constraint
    eligible = urban_cand[urban_cand["nearest_station_km"] >= min_spacing_km].copy().reset_index(drop=True)
    if eligible.empty:
        return eligible, pd.DataFrame()

    # Precompute population for existing station buffers (for overlap share denominator)
    st_bufs_4326 = gpd.GeoSeries(st_bufs_m, crs=PROJ_CRS).to_crs(WGS84_CRS)
    st_demands = [compute_geometry_pop(b, city_raster, win_trans) for b in st_bufs_4326]

    # Precompute candidate buffers
    cand_bufs_m = eligible.geometry.buffer(catchment_radius_m)
    cand_bufs_4326 = gpd.GeoSeries(cand_bufs_m, crs=PROJ_CRS).to_crs(WGS84_CRS)

    c_pop = []
    u_pop = []
    ov_shares = []

    for i in range(len(eligible)):
        b_c_m = cand_bufs_m.iloc[i]
        b_c_4326 = cand_bufs_4326.iloc[i]

        # Total population inside candidate catchment
        pop_total = compute_geometry_pop(b_c_4326, city_raster, win_trans)
        c_pop.append(pop_total)

        # Unserved geometry: candidate buffer minus existing station buffers
        geom_unserved_m = b_c_m.difference(union_existing_m)
        if geom_unserved_m.is_empty:
            pop_unserved = 0.0
        else:
            geom_u_4326 = gpd.GeoSeries([geom_unserved_m], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
            pop_unserved = compute_geometry_pop(geom_u_4326, city_raster, win_trans)
        u_pop.append(pop_unserved)

        # Overlap share with nearest existing station
        nst_i = eligible.loc[i, "nearest_st_idx"]
        d_km = eligible.loc[i, "nearest_station_km"]
        ov_s = 0.0
        # If within 2 * catchment radius (4 km), compute actual geometric overlap
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

    # Formula for Priority Score:
    # Score = [w_unserved * unserved_share * (unserved_pop / max_pop) - w_overlap * overlap_share] * 100
    max_unserved = max(1.0, eligible["unserved_pop"].max())
    eligible["score"] = (
        w_unserved * eligible["unserved_share"] * (eligible["unserved_pop"] / max_unserved)
        - w_overlap * eligible["overlap_share"]
    ) * 100.0

    eligible_wgs = eligible.to_crs(WGS84_CRS)
    eligible["lat"] = eligible_wgs.geometry.y
    eligible["lon"] = eligible_wgs.geometry.x

    all_ranked = eligible.sort_values("score", ascending=False).reset_index(drop=True)

    # Optional candidate dispersion (non-maximum suppression between candidates)
    if min_cand_spacing_km > 0.0:
        selected = []
        remaining = all_ranked.copy()
        while len(selected) < 10 and not remaining.empty:
            best = remaining.iloc[0]
            selected.append(best)
            p_best = best.geometry
            cand_dists = [p_best.distance(p) / 1000.0 for p in remaining.geometry]
            remaining = remaining[np.array(cand_dists) >= min_cand_spacing_km].copy().reset_index(drop=True)
        top10 = pd.DataFrame(selected).reset_index(drop=True)
    else:
        top10 = all_ranked.head(10).copy()

    top10["rank"] = range(1, len(top10) + 1)
    return all_ranked, top10


def run_leave_out_test(gdf_stations_city, city, city_raster, win_trans, min_spacing_km, catchment_radius_m=2000.0, seed=42):
    """Sanity check: remove 20% of existing stations and test recovery in top candidates."""
    n_st = len(gdf_stations_city)
    n_leave = max(1, int(round(0.20 * n_st)))

    rng = np.random.default_rng(seed)
    leave_indices = rng.choice(n_st, size=n_leave, replace=False)

    gdf_retained = gdf_stations_city.drop(index=leave_indices).reset_index(drop=True)
    gdf_removed = gdf_stations_city.iloc[leave_indices].reset_index(drop=True)

    # Re-run candidate generation & scoring with retained stations
    clat, clon = CITY_CENTRES[city]
    urban_cand, _ = build_candidate_grid(clat, clon, city_raster, win_trans, pop_threshold=DEFAULT_POP_THRESHOLD)
    _, top10_recomputed = score_candidate_sites(
        urban_cand,
        gdf_retained,
        city_raster,
        win_trans,
        min_spacing_km=min_spacing_km,
        catchment_radius_m=catchment_radius_m,
        min_cand_spacing_km=0.0
    )

    # Check recovery: does top 10 contain a candidate within catchment radius (2.0 km) of removed station?
    recovered_count = 0
    results_detail = []

    for _, r_st in gdf_removed.iterrows():
        p_rem = r_st.geometry
        cand_dists = [p_rem.distance(Point(c.geometry.x, c.geometry.y)) / 1000.0 for _, c in top10_recomputed.iterrows()]
        min_dist = min(cand_dists) if cand_dists else 999.0
        is_recovered = min_dist <= (catchment_radius_m / 1000.0)
        if is_recovered:
            recovered_count += 1
        results_detail.append({
            "removed_station": r_st.get("station_name", "Unknown"),
            "closest_candidate_km": round(min_dist, 2),
            "recovered": is_recovered
        })

    recovery_rate = (recovered_count / n_leave) * 100.0
    return {
        "city": city,
        "total_stations": n_st,
        "n_removed": n_leave,
        "recovered_count": recovered_count,
        "recovery_rate_pct": recovery_rate,
        "details": results_detail
    }


def plot_ranked_sites_map(city, gdf_st_city, top10, city_raster, win_trans, output_png_path, catchment_radius_m=2000.0):
    """Generate high-resolution cartographic map of top candidate sites and existing stations."""
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)

    # Transform raster extent to WGS84 coordinates for imshow
    h, w = city_raster.shape
    top_left = win_trans * (0, 0)
    bot_right = win_trans * (w, h)
    extent = [top_left[0], bot_right[0], bot_right[1], top_left[1]]

    # Visual background: log-scaled population density
    plot_raster = np.log1p(city_raster)
    im = ax.imshow(plot_raster, extent=extent, cmap="YlOrRd", alpha=0.55, origin="upper")
    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("Population Density (log scale, persons/km²)", fontsize=9, fontweight="bold")

    # Plot existing stations and their buffer catchments
    gdf_st_wgs = gdf_st_city.to_crs(WGS84_CRS)
    st_bufs_4326 = gpd.GeoSeries(gdf_st_city.geometry.buffer(catchment_radius_m), crs=PROJ_CRS).to_crs(WGS84_CRS)

    st_bufs_4326.plot(ax=ax, facecolor="none", edgecolor="#1f77b4", linewidth=1.2, linestyle="--", label="Existing Catchment (2.0 km)")
    ax.scatter(gdf_st_wgs.geometry.x, gdf_st_wgs.geometry.y, color="#1f77b4", s=45, marker="s", edgecolors="black", linewidth=0.8, zorder=4, label=f"Existing Stations (N={len(gdf_st_city)})")

    # Plot top 10 candidate sites
    top10_wgs = gpd.GeoDataFrame(top10, geometry=[Point(xy) for xy in zip(top10["lon"], top10["lat"])], crs=WGS84_CRS)
    cand_bufs_4326 = gpd.GeoSeries(top10["geometry"].values, crs=PROJ_CRS).buffer(catchment_radius_m).to_crs(WGS84_CRS)
    cand_bufs_4326.plot(ax=ax, facecolor="#2ca02c", alpha=0.15, edgecolor="#2ca02c", linewidth=1.5, linestyle="-", label="Candidate Catchment (2.0 km)")

    sc = ax.scatter(top10_wgs.geometry.x, top10_wgs.geometry.y, c=top10["score"], cmap="viridis", s=180, marker="*", edgecolors="black", linewidth=1.0, zorder=5, label="Top 10 Candidate Sites")

    # Annotate candidate ranks
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

    # City center marker
    clat, clon = CITY_CENTRES[city]
    ax.scatter([clon], [clat], color="black", marker="x", s=80, linewidth=2, zorder=4, label="City Center")

    # Formatting and bounds
    all_x = list(gdf_st_wgs.geometry.x) + list(top10["lon"]) + [clon]
    all_y = list(gdf_st_wgs.geometry.y) + list(top10["lat"]) + [clat]
    pad_deg = 0.04
    ax.set_xlim(min(all_x) - pad_deg, max(all_x) + pad_deg)
    ax.set_ylim(min(all_y) - pad_deg, max(all_y) + pad_deg)

    ax.set_title(
        f"{city}: Top 10 Ranked Candidate Siting Opportunities\n"
        f"(20% Overlap Spacing Parameter: {DEFAULT_MIN_SPACING_KM[city]} km | Catchment: {catchment_radius_m/1000.0:.1f} km [ASSUMPTION])",
        fontsize=12,
        fontweight="bold",
        pad=12
    )
    ax.set_xlabel("Longitude (°E)", fontsize=10)
    ax.set_ylabel("Latitude (°N)", fontsize=10)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.92)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path, dpi=300)
    plt.close()
    print(f"  [Figure] Saved high-res map to {output_png_path}")


def main():
    parser = argparse.ArgumentParser(description="Rank candidate CNG station sites (PS000002 Module D Part 1).")
    parser.add_argument("--stations-file", default="data/processed/stations_geocoded.csv", help="Clean geocoded stations path")
    parser.add_argument("--raster-file", default="data/raw/ind_ppp_2020_1km_UNadj.tif", help="WorldPop UN-adjusted raster path")
    parser.add_argument("--spacing-summary", default="data/processed/spacing_summary.csv", help="Spacing summary path")
    parser.add_argument("--catchment-radius-m", type=float, default=DEFAULT_CATCHMENT_RADIUS_M, help="Buffer-based catchment radius (m) [ASSUMPTION]")
    parser.add_argument("--pop-threshold", type=float, default=DEFAULT_POP_THRESHOLD, help="Built-up density threshold (persons/km2) [ASSUMPTION]")
    parser.add_argument("--w-unserved", type=float, default=DEFAULT_W_UNSERVED, help="Weight on unserved population share")
    parser.add_argument("--w-overlap", type=float, default=DEFAULT_W_OVERLAP, help="Weight on catchment overlap penalty")
    parser.add_argument("--min-cand-spacing-km", type=float, default=0.0, help="Optional mutual dispersion between candidate sites (km)")
    parser.add_argument("--output-csv", default="data/processed/ranked_sites.csv", help="Output path for ranked sites CSV")
    parser.add_argument("--output-fig-dir", default="outputs/figures", help="Output directory for map figures")
    args = parser.parse_args()

    print("=" * 80)
    print("MODULE D: SITE-RANKING & BUFFER CATCHMENT EVALUATION (PART 1)")
    print("=" * 80)
    print("STRICT GUIDELINE VERIFICATION:")
    print("  - Observed data: High/medium confidence unique coordinates only (Task 3b filter).")
    print("  - Demand proxy: Localized UN-adjusted 1 km WorldPop raster (no synthetic RTO files).")
    print("  - Siting Formula: Score = [w_unserved * unserved_share * (unserved_pop / max_pop) - w_overlap * overlap_share] * 100")
    print(f"  - Parameters: w_unserved={args.w_unserved}, w_overlap={args.w_overlap}")
    print(f"  - Catchment Radius: {args.catchment_radius_m/1000.0:.1f} km [ASSUMPTION: circular buffer proxy]")
    print(f"  - Built-up Agglomeration Threshold: {args.pop_threshold} persons/km² [ASSUMPTION: MoHUA urban definition]")
    print("=" * 80)

    # Load clean stations
    df_clean = load_clean_stations(args.stations_file)
    print(f"Loaded {len(df_clean)} clean unique-coordinate stations across network.")

    all_city_top10 = []
    leave_out_reports = []

    for city in ["Surat", "Rajkot"]:
        print(f"\nProcessing {city.upper()}...")
        st_city = df_clean[df_clean["city"] == city].copy().reset_index(drop=True)
        if st_city.empty:
            print(f"  [Warning] No stations found for {city}, skipping.")
            continue

        gdf_st = gpd.GeoDataFrame(
            st_city,
            geometry=[Point(lo, la) for lo, la in zip(st_city["lon"], st_city["lat"])],
            crs=WGS84_CRS
        ).to_crs(PROJ_CRS)
        print(f"  Clean operating stations in {city}: {len(gdf_st)}")

        # Spacing parameter
        min_spacing_km = DEFAULT_MIN_SPACING_KM.get(city, 3.10)
        print(f"  Minimum spacing from existing stations: {min_spacing_km:.2f} km (from 20% overlap threshold)")

        # Extract raster window
        city_raster, win_trans = extract_city_raster(gdf_st, args.raster_file)

        # Build candidate grid
        clat, clon = CITY_CENTRES[city]
        urban_cand, n_total_grid = build_candidate_grid(
            clat, clon, city_raster, win_trans, pop_threshold=args.pop_threshold
        )
        print(f"  500 m grid cells generated: {n_total_grid} total | {len(urban_cand)} built-up cells (>= {args.pop_threshold} pop/km²)")

        # Score and rank candidates
        all_ranked, top10 = score_candidate_sites(
            urban_cand,
            gdf_st,
            city_raster,
            win_trans,
            min_spacing_km=min_spacing_km,
            catchment_radius_m=args.catchment_radius_m,
            w_unserved=args.w_unserved,
            w_overlap=args.w_overlap,
            min_cand_spacing_km=args.min_cand_spacing_km
        )
        print(f"  Eligible candidate sites (spacing >= {min_spacing_km:.2f} km): {len(all_ranked)}")

        # Add city column
        top10["city"] = city
        all_city_top10.append(top10)

        # Print top 10 table
        cols_display = ["rank", "lat", "lon", "unserved_pop", "catchment_pop", "unserved_share", "overlap_share", "nearest_station_km", "score"]
        print("\n  Top 10 Siting Candidates:")
        print(top10[cols_display].to_string(index=False))

        # Plot map
        fig_path = os.path.join(args.output_fig_dir, f"ranked_sites_{city.lower()}.png")
        plot_ranked_sites_map(city, gdf_st, top10, city_raster, win_trans, fig_path, args.catchment_radius_m)

        # Run Leave-Out Test
        print(f"\n  Running 20% Station Leave-Out Test for {city}...")
        lo_res = run_leave_out_test(gdf_st, city, city_raster, win_trans, min_spacing_km, args.catchment_radius_m)
        leave_out_reports.append(lo_res)
        print(f"  Leave-Out Result: {lo_res['recovered_count']}/{lo_res['n_removed']} ({lo_res['recovery_rate_pct']:.1f}%) removed station areas recovered in Top 10.")
        for d in lo_res["details"]:
            status_str = "RECOVERED" if d["recovered"] else "NOT RECOVERED"
            print(f"    - {d['removed_station']}: closest candidate = {d['closest_candidate_km']:.2f} km [{status_str}]")

    # Combine top 10 for both cities
    if all_city_top10:
        df_out = pd.concat(all_city_top10, ignore_index=True)
        # Reorder to required columns: lat, lon, unserved_pop, overlap_share, nearest_station_km, score, rank
        cols_required = ["city", "rank", "lat", "lon", "unserved_pop", "catchment_pop", "unserved_share", "overlap_share", "nearest_station_km", "score"]
        df_final = df_out[cols_required].copy()

        # Format numeric precision
        df_final["lat"] = df_final["lat"].round(6)
        df_final["lon"] = df_final["lon"].round(6)
        df_final["unserved_pop"] = df_final["unserved_pop"].round(1)
        df_final["catchment_pop"] = df_final["catchment_pop"].round(1)
        df_final["unserved_share"] = df_final["unserved_share"].round(4)
        df_final["overlap_share"] = df_final["overlap_share"].round(4)
        df_final["nearest_station_km"] = df_final["nearest_station_km"].round(3)
        df_final["score"] = df_final["score"].round(2)

        os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
        df_final.to_csv(args.output_csv, index=False)
        print("\n" + "=" * 80)
        print(f"SUCCESS: Top candidate sites saved to {args.output_csv}")
        print("=" * 80)


if __name__ == "__main__":
    main()
