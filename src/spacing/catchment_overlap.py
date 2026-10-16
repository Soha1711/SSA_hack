"""
src/spacing/catchment_overlap.py
--------------------------------
Geographic demand-overlap and station spacing analysis for Gujarat Gas Limited (PS000002, Module C).

IMPORTANT METHODOLOGICAL AND ASSUMPTION DISCLAIMER:
---------------------------------------------------
1. Road-Network Isolines:
   Road-network drivetime isolines could NOT be constructed because Overpass API queries failed
   due to server-side rate limits and network timeouts on large-scale road network extractions.
   Therefore, this analysis uses circular BUFFER-BASED CATCHMENTS in metric UTM Zone 43N coordinates.

2. Circuity Factor & Driving Speed are ASSUMPTIONS, Not Measurements:
   - Circuity factor (ratio of road network distance to Euclidean straight-line distance) is ASSUMED to be 1.28.
     Source citation: Ballou, R. H., Rahardja, H., & Sakai, N. (2002). "Selected issues in Euclidean distance
     estimating for logistics applications." Transportation Research Part A: Policy and Practice, 36(3), 193-210.
     (Ballou et al. document road circuity typically ranging from 1.20 to 1.40 for regional and urban street networks).
   - Urban driving speed is ASSUMED to be 25 km/h.
   - These parameters are modeling assumptions, NOT local road-network measurements.

3. Geographic Demand-Overlap vs. Sales Cannibalisation:
   This module implements a purely GEOGRAPHIC DEMAND-OVERLAP method based on spatial buffer-based catchments
   and WorldPop 2020 UN-adjusted population distribution. It is NOT an observed sales drop and does NOT
   represent empirical station-level sales cannibalisation. Overlap share reflects geographic demand co-exposure
   between station service areas.

Data Inputs:
- data/processed/stations_geocoded.csv: Geocoded Gujarat Gas stations.
- data/raw/osm_cng_stations_gujarat.csv: Competitor CNG stations from OpenStreetMap (illustrative).
- data/raw/ind_ppp_2020_1km_UNadj.tif: WorldPop UN-adjusted population raster (2020, 1 km, CC BY 4.0).

Outputs:
- data/processed/spacing_results.csv: Pairwise distances and overlap shares across 7 assumed catchment radii.
- data/processed/spacing_summary.csv: Threshold distances at 30%, 20%, and 10% overlap, expressed as multiples of radius (k*R), with 90% bootstrap intervals.
- outputs/figures/surat_stations_map.png: Map of Surat network, buffer-based catchments, and population density.
- outputs/figures/rajkot_stations_map.png: Map of Rajkot network, buffer-based catchments, and population density.
- outputs/figures/nn_distance_hist.png: Nearest-neighbour distance distributions (clean, non-coincident stations).
- outputs/figures/overlap_vs_distance.png: Overlap vs distance decay curves for all radii on one figure with bootstrap confidence bands.
"""

import os
import math
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D


# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
PROJ_CRS = "EPSG:32643"  # UTM Zone 43N (metric projection for Gujarat)
WGS84_CRS = "EPSG:4326"

# Circuity assumption cited from Ballou et al. (2002)
CIRCUITY_FACTOR = 1.28

# Sensitivity analysis radii: Urban (1.5, 2.0, 2.5, 3.0 km) and Corridor (4.0, 6.0, 8.0 km)
RADII_SPECS = [
    {"label": "1.5km (urban)", "radius_km": 1.5, "radius_m": 1500.0, "env": "urban", "color": "#74a9cf"},
    {"label": "2.0km (urban)", "radius_km": 2.0, "radius_m": 2000.0, "env": "urban", "color": "#2b8cbe"},
    {"label": "2.5km (urban)", "radius_km": 2.5, "radius_m": 2500.0, "env": "urban", "color": "#045a8d"},
    {"label": "3.0km (urban)", "radius_km": 3.0, "radius_m": 3000.0, "env": "urban", "color": "#023858"},
    {"label": "4.0km (corridor)", "radius_km": 4.0, "radius_m": 4000.0, "env": "corridor", "color": "#feb24c"},
    {"label": "6.0km (corridor)", "radius_km": 6.0, "radius_m": 6000.0, "env": "corridor", "color": "#f03b20"},
    {"label": "8.0km (corridor)", "radius_km": 8.0, "radius_m": 8000.0, "env": "corridor", "color": "#bd0026"},
]

CITY_CENTRES = {
    "Surat": (21.1702, 72.8311),
    "Rajkot": (22.3039, 70.8022),
    "Ahmedabad": (23.0225, 72.5714),
    "Vadodara": (22.3072, 73.1812),
}


def load_clean_data() -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Load station locations, apply strict geocoding quality controls, and load competitor data.

    Quality controls:
    1. Must have geocoded == True.
    2. Must have high or medium confidence (drops all pincode_district centroid matches).
    3. Strictly unique coordinates: drop any station sharing identical coordinates with another.
       (If several stations share a point, keep none unless the address clearly identifies one).
    """
    geocoded_path = "data/processed/stations_geocoded.csv"
    osm_path = "data/raw/osm_cng_stations_gujarat.csv"
    raster_path = "data/raw/ind_ppp_2020_1km_UNadj.tif"

    if not os.path.exists(geocoded_path):
        raise FileNotFoundError(f"Missing geocoded stations: {geocoded_path}")
    if not os.path.exists(osm_path):
        raise FileNotFoundError(f"Missing OSM stations: {osm_path}")
    if not os.path.exists(raster_path):
        raise FileNotFoundError(f"Missing WorldPop population raster: {raster_path}")

    df_raw = pd.read_csv(geocoded_path)
    print(f"Total raw station directory records: {len(df_raw)}")

    # 1. High or medium confidence only
    hm_mask = df_raw["geocoded"] & df_raw["confidence"].isin(["high", "medium"])
    df_hm = df_raw[hm_mask].copy()

    # 2. Check duplicate coordinates across all geocoded stations
    geocoded_pts = df_raw[df_raw["geocoded"] == True]
    pt_counts = geocoded_pts.groupby(["lat", "lon"]).size()
    dup_coords = pt_counts[pt_counts > 1].index

    # 3. Retain only stations with unique coordinates
    clean_mask = ~df_hm.set_index(["lat", "lon"]).index.isin(dup_coords)
    df_clean = df_hm[clean_mask].copy().reset_index(drop=True)

    print(f"Stations after dropping low-confidence and shared-coordinate points: {len(df_clean)}")
    counts_by_city = df_clean["city"].value_counts().to_dict()
    for c, cnt in counts_by_city.items():
        print(f"  - {c}: {cnt} stations")

    df_osm = pd.read_csv(osm_path)
    df_comp = df_osm[df_osm["cgd_company"] != "Gujarat Gas"].copy()

    return df_clean, df_comp, raster_path


def compute_nearest_neighbours(gdf_city: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute straight-line and assumed road nearest-neighbour distance for every station.
    """
    n = len(gdf_city)
    nn_straight = []
    nn_road = []

    for i in range(n):
        p_i = gdf_city.geometry.iloc[i]
        dists = [p_i.distance(gdf_city.geometry.iloc[j]) / 1000.0 for j in range(n) if i != j]
        min_d = min(dists) if dists else 0.0
        nn_straight.append(min_d)
        nn_road.append(min_d * CIRCUITY_FACTOR)

    gdf_city["nn_straight_km"] = nn_straight
    gdf_city["nn_road_km"] = nn_road
    return gdf_city


def extract_city_population_raster(raster_path: str, gdf_city: gpd.GeoDataFrame) -> Tuple[np.ndarray, rasterio.Affine]:
    """
    Extract a cropped in-memory population array for the city's bounding area with padding.
    """
    bounds = gdf_city.to_crs(WGS84_CRS).total_bounds
    # Add 0.20 deg (~22 km) padding to cover large 8 km corridor buffers
    minx, miny, maxx, maxy = bounds[0] - 0.20, bounds[1] - 0.20, bounds[2] + 0.20, bounds[3] + 0.20

    with rasterio.open(raster_path) as src:
        win = from_bounds(minx, miny, maxx, maxy, src.transform)
        arr = src.read(1, window=win)
        win_transform = src.window_transform(win)
        arr = np.where(arr < 0, 0, arr)
        arr = np.nan_to_num(arr, nan=0.0)

    return arr, win_transform


def get_polygon_population(geom_4326, city_raster: np.ndarray, win_transform: rasterio.Affine) -> float:
    """Sum population pixels within a WGS84 polygon geometry."""
    if geom_4326.is_empty:
        return 0.0
    mask = geometry_mask([geom_4326], out_shape=city_raster.shape, transform=win_transform, invert=True)
    return float(np.sum(city_raster[mask]))


def interpolate_thresholds(dist_m: np.ndarray, ov_m: np.ndarray, r_max: float) -> Dict[float, float]:
    """
    Linearly interpolate the distance threshold at which mean overlap drops below 30%, 20%, 10%.
    """
    thresholds = {}
    for th in [0.30, 0.20, 0.10]:
        below = np.where(ov_m < th)[0]
        if len(below) > 0:
            first_idx = below[0]
            if first_idx > 0:
                d_prev, d_curr = dist_m[first_idx - 1], dist_m[first_idx]
                o_prev, o_curr = ov_m[first_idx - 1], ov_m[first_idx]
                if o_curr != o_prev:
                    d_th = d_prev + (th - o_prev) * (d_curr - d_prev) / (o_curr - o_prev)
                else:
                    d_th = d_curr
            else:
                d_th = dist_m[0]
            d_th = max(0.1, min(r_max, d_th))
        else:
            d_th = r_max
        thresholds[th] = float(d_th)
    return thresholds


def fast_bootstrap_thresholds(
    dist_mat: np.ndarray,
    ov_mat: np.ndarray,
    r_km: float,
    n_boot: int = 500,
    seed: int = 42
) -> Dict[float, Tuple[float, float]]:
    """
    Vectorized station bootstrap (500 draws) to construct 90% confidence intervals [P5, P95]
    for distance thresholds where mean overlap falls below 30%, 20%, 10%.
    """
    n = dist_mat.shape[0]
    r_max = 2.0 * r_km
    bins = np.linspace(0, r_max, 25)
    n_bins = len(bins) - 1

    i_upper, j_upper = np.triu_indices(n, k=1)
    rng = np.random.default_rng(seed)
    boot_ths = {0.30: [], 0.20: [], 0.10: []}

    for _ in range(n_boot):
        sample = rng.choice(n, size=n, replace=True)
        s1 = sample[i_upper]
        s2 = sample[j_upper]
        mask_distinct = s1 != s2
        if not np.any(mask_distinct):
            continue

        p_d = dist_mat[s1[mask_distinct], s2[mask_distinct]]
        p_ov = ov_mat[s1[mask_distinct], s2[mask_distinct]]

        mask_rmax = p_d <= r_max
        p_d = p_d[mask_rmax]
        p_ov = p_ov[mask_rmax]

        if len(p_d) < 4:
            continue

        bin_idx = np.clip(np.digitize(p_d, bins) - 1, 0, n_bins - 1)
        counts = np.bincount(bin_idx, minlength=n_bins)
        valid = counts > 0
        if not np.any(valid):
            continue

        dist_sums = np.bincount(bin_idx, weights=p_d, minlength=n_bins)
        ov_sums = np.bincount(bin_idx, weights=p_ov, minlength=n_bins)

        dist_m = dist_sums[valid] / counts[valid]
        ov_m = ov_sums[valid] / counts[valid]

        th_res = interpolate_thresholds(dist_m, ov_m, r_max)
        for th in [0.30, 0.20, 0.10]:
            boot_ths[th].append(th_res[th])

    ci_res = {}
    for th in [0.30, 0.20, 0.10]:
        vals = boot_ths[th]
        p5 = float(np.percentile(vals, 5)) if vals else 0.0
        p95 = float(np.percentile(vals, 95)) if vals else r_max
        ci_res[th] = (p5, p95)
    return ci_res


def analyze_city_multi_radius(
    city: str,
    gdf_city: gpd.GeoDataFrame,
    city_raster: np.ndarray,
    win_trans: rasterio.Affine,
    df_comp: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any], gpd.GeoDataFrame, Tuple[int, int]]:
    """
    Run buffer-based catchment overlap across all 7 radii for a single city.
    """
    n = len(gdf_city)
    dist_mat = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dist_mat[i, j] = gdf_city.geometry.iloc[i].distance(gdf_city.geometry.iloc[j]) / 1000.0

    pairwise_records = []
    summary_records = []
    curves_data = {}

    for spec in RADII_SPECS:
        r_km = spec["radius_km"]
        r_m = spec["radius_m"]
        env = spec["env"]
        label = spec["label"]

        bufs_m = gdf_city.geometry.buffer(r_m)
        bufs_4326 = gpd.GeoSeries(bufs_m, crs=PROJ_CRS).to_crs(WGS84_CRS)
        demands = [get_polygon_population(b, city_raster, win_trans) for b in bufs_4326]

        ov_mat = np.zeros((n, n))
        p_d_list = []
        p_ov_list = []

        for i in range(n):
            for j in range(i + 1, n):
                d_km = dist_mat[i, j]
                ov_s = 0.0
                p_inter = 0.0
                if d_km * 1000.0 < 2 * r_m:
                    inter = bufs_m.iloc[i].intersection(bufs_m.iloc[j])
                    if not inter.is_empty:
                        inter_4326 = gpd.GeoSeries([inter], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
                        p_inter = get_polygon_population(inter_4326, city_raster, win_trans)
                        min_d = min(demands[i], demands[j])
                        ov_s = min(1.0, p_inter / min_d if min_d > 0 else 0.0)

                ov_mat[i, j] = ov_s
                ov_mat[j, i] = ov_s

                if d_km <= 2 * r_km:
                    p_d_list.append(d_km)
                    p_ov_list.append(ov_s)

                pairwise_records.append({
                    "city": city,
                    "radius_km": r_km,
                    "environment": env,
                    "station_a": gdf_city.loc[i, "station_name"],
                    "station_b": gdf_city.loc[j, "station_name"],
                    "distance_straight_km": round(d_km, 3),
                    "distance_road_km": round(d_km * CIRCUITY_FACTOR, 3),
                    "overlap_share": round(ov_s, 4),
                    "overlap_population": round(p_inter, 1),
                })

        # Binned average curve
        p_d_arr = np.array(p_d_list)
        p_ov_arr = np.array(p_ov_list)
        r_max = 2.0 * r_km
        bins = np.linspace(0, r_max, 25)
        n_bins = len(bins) - 1
        bin_idx = np.clip(np.digitize(p_d_arr, bins) - 1, 0, n_bins - 1)
        counts = np.bincount(bin_idx, minlength=n_bins)
        valid = counts > 0
        dist_sums = np.bincount(bin_idx, weights=p_d_arr, minlength=n_bins)
        ov_sums = np.bincount(bin_idx, weights=p_ov_arr, minlength=n_bins)
        dist_m = dist_sums[valid] / counts[valid]
        ov_m = ov_sums[valid] / counts[valid]

        curves_data[label] = {
            "dist": dist_m,
            "ov": ov_m,
            "raw_d": p_d_arr,
            "raw_ov": p_ov_arr,
            "spec": spec,
        }

        # Thresholds and Bootstrap
        ths = interpolate_thresholds(dist_m, ov_m, r_max)
        ci_res = fast_bootstrap_thresholds(dist_mat, ov_mat, r_km, n_boot=500, seed=42)

        for th_val in [0.30, 0.20, 0.10]:
            d_s = ths[th_val]
            d_r = d_s * CIRCUITY_FACTOR
            k = d_s / r_km
            p5, p95 = ci_res[th_val]
            p5_r, p95_r = p5 * CIRCUITY_FACTOR, p95 * CIRCUITY_FACTOR
            k_p5, k_p95 = p5 / r_km, p95 / r_km
            summary_records.append({
                "city": city,
                "environment": env,
                "radius_km": r_km,
                "overlap_threshold_pct": int(th_val * 100),
                "spacing_straight_km": round(d_s, 2),
                "spacing_road_km": round(d_r, 2),
                "multiple_k": round(k, 2),
                "ci90_straight_km": f"[{p5:.2f}, {p95:.2f}]",
                "ci90_road_km": f"[{p5_r:.2f}, {p95_r:.2f}]",
                "ci90_multiple_k": f"[{k_p5:.2f}, {k_p95:.2f}]",
                "ci90_p5_straight_km": round(p5, 2),
                "ci90_p95_straight_km": round(p95, 2),
                "ci90_p5_road_km": round(p5_r, 2),
                "ci90_p95_road_km": round(p95_r, 2),
            })

    # Competitor interaction (illustrative)
    c_lat, c_lon = CITY_CENTRES.get(city, (gdf_city["lat"].mean(), gdf_city["lon"].mean()))
    p_center = Point(c_lon, c_lat)
    gdf_center = gpd.GeoDataFrame(geometry=[p_center], crs=WGS84_CRS).to_crs(PROJ_CRS)
    c_pt = gdf_center.geometry.iloc[0]

    gdf_comp_m = gpd.GeoDataFrame(
        df_comp,
        geometry=[Point(lon, lat) for lon, lat in zip(df_comp["lon"], df_comp["lat"])],
        crs=WGS84_CRS
    ).to_crs(PROJ_CRS)
    gdf_comp_m["dist_center_km"] = [g.distance(c_pt) / 1000.0 for g in gdf_comp_m.geometry]
    city_comp = gdf_comp_m[gdf_comp_m["dist_center_km"] <= 30].copy().reset_index(drop=True)

    comp_exp_2km = 0
    comp_exp_6km = 0
    if len(city_comp) > 0:
        c_buf_2km = city_comp.geometry.buffer(2000.0)
        c_buf_6km = city_comp.geometry.buffer(6000.0)
        buf_2km_gg = gdf_city.geometry.buffer(2000.0)
        buf_6km_gg = gdf_city.geometry.buffer(6000.0)
        for i in range(n):
            if any(buf_2km_gg.iloc[i].intersects(c_buf_2km.iloc[k]) for k in range(len(city_comp))):
                comp_exp_2km += 1
            if any(buf_6km_gg.iloc[i].intersects(c_buf_6km.iloc[k]) for k in range(len(city_comp))):
                comp_exp_6km += 1

    return (
        pd.DataFrame(pairwise_records),
        pd.DataFrame(summary_records),
        curves_data,
        city_comp,
        (comp_exp_2km, comp_exp_6km),
    )


def plot_overlap_vs_distance_all_radii(
    curves_by_city: Dict[str, Dict[str, Any]],
    summary_df: pd.DataFrame,
    out_path: str
):
    """
    Plot geographic demand-overlap decay curves for all 7 assumed radii on ONE figure.
    Includes 30%, 20%, 10% threshold lines and multiple annotations (k*R).
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), dpi=300)

    for ax, city in zip(axes, ["Surat", "Rajkot"]):
        city_curves = curves_by_city[city]

        # Plot curves for each radius
        for spec in RADII_SPECS:
            label = spec["label"]
            r_km = spec["radius_km"]
            c_data = city_curves[label]
            dist_m = c_data["dist"]
            ov_m = c_data["ov"] * 100.0
            color = spec["color"]
            linestyle = "-" if spec["env"] == "urban" else "--"
            linewidth = 2.4 if r_km in [2.0, 6.0] else 1.6

            line_lbl = f"R={r_km:.1f} km ({spec['env'].capitalize()})"
            ax.plot(dist_m, ov_m, color=color, linestyle=linestyle, linewidth=linewidth, label=line_lbl)

            # Scatter points for raw pairs (faint)
            if r_km in [2.0, 6.0]:
                ax.scatter(c_data["raw_d"], c_data["raw_ov"] * 100.0, alpha=0.15, s=12, color=color)

        # Threshold lines
        ax.axhline(30, color="#525252", linestyle=":", linewidth=1.1, alpha=0.8)
        ax.axhline(20, color="#525252", linestyle="--", linewidth=1.1, alpha=0.8)
        ax.axhline(10, color="#525252", linestyle="-.", linewidth=1.1, alpha=0.8)

        # Text labels for thresholds
        ax.text(15.2, 30.5, "30% Overlap", fontsize=7.5, color="#525252", va="bottom")
        ax.text(15.2, 20.5, "20% Overlap", fontsize=7.5, color="#525252", va="bottom")
        ax.text(15.2, 10.5, "10% Overlap", fontsize=7.5, color="#525252", va="bottom")

        # Summary box for baseline urban (R=2.0 km) and baseline corridor (R=6.0 km)
        sub_2 = summary_df[(summary_df["city"] == city) & (summary_df["radius_km"] == 2.0)]
        sub_6 = summary_df[(summary_df["city"] == city) & (summary_df["radius_km"] == 6.0)]

        k30_u = sub_2[sub_2["overlap_threshold_pct"] == 30]["multiple_k"].values[0]
        k10_u = sub_2[sub_2["overlap_threshold_pct"] == 10]["multiple_k"].values[0]
        d30_u = sub_2[sub_2["overlap_threshold_pct"] == 30]["spacing_straight_km"].values[0]
        d10_u = sub_2[sub_2["overlap_threshold_pct"] == 10]["spacing_straight_km"].values[0]

        k30_c = sub_6[sub_6["overlap_threshold_pct"] == 30]["multiple_k"].values[0]
        k10_c = sub_6[sub_6["overlap_threshold_pct"] == 10]["multiple_k"].values[0]
        d30_c = sub_6[sub_6["overlap_threshold_pct"] == 30]["spacing_straight_km"].values[0]
        d10_c = sub_6[sub_6["overlap_threshold_pct"] == 10]["spacing_straight_km"].values[0]

        box_text = (
            f"Under Assumed Catchment Radius R:\n"
            f"• Urban Baseline (R = 2.0 km):\n"
            f"   Overlap < 30% at {d30_u:.2f} km (~{k30_u:.2f}·R)\n"
            f"   Overlap < 10% at {d10_u:.2f} km (~{k10_u:.2f}·R)\n"
            f"• Corridor Baseline (R = 6.0 km):\n"
            f"   Overlap < 30% at {d30_c:.2f} km (~{k30_c:.2f}·R)\n"
            f"   Overlap < 10% at {d10_c:.2f} km (~{k10_c:.2f}·R)"
        )
        ax.text(
            0.97, 0.96,
            box_text,
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#08519c", alpha=0.92, lw=0.8)
        )

        ax.set_title(f"{city} Network: Overlap Decay Across All Catchment Radii", fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel("Station Straight-Line Distance (km)", fontsize=9.5)
        ax.set_ylabel("Demand Overlap Share (%)", fontsize=9.5)
        ax.set_ylim(-2, 105)
        ax.set_xlim(0, 16.5)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(loc="lower left", fontsize=7.5, framealpha=0.92, ncol=2)

    fig.suptitle(
        "Sensitivity to Assumed Catchment Radius (Urban: 1.5–3.0 km; Corridor: 4.0–8.0 km)\n"
        "Under assumed catchment radius R, overlap falls below X% at about k·R — NOT an observed sales effect",
        fontsize=12, fontweight="bold", y=1.03
    )
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved overlap vs distance plot: {out_path}")


def plot_nearest_neighbour_histogram(gdf_surat: gpd.GeoDataFrame, gdf_rajkot: gpd.GeoDataFrame, out_path: str):
    """
    Plot nearest-neighbour distance distributions for clean, non-duplicated station networks.
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    for ax, gdf, city, color in zip(axes, [gdf_surat, gdf_rajkot], ["Surat", "Rajkot"], ["#1f78b4", "#33a02c"]):
        dists_straight = gdf["nn_straight_km"]
        dists_road = gdf["nn_road_km"]

        n_coincident = sum(1 for d in dists_straight if d == 0.0)
        bins = np.linspace(0, max(12, math.ceil(dists_road.max())), 25)

        ax.hist(dists_straight, bins=bins, alpha=0.65, color=color, edgecolor="black", label=f"Straight-line (median={np.median(dists_straight):.2f} km)")
        ax.hist(dists_road, bins=bins, alpha=0.45, color="orange", edgecolor="darkorange", linestyle="--", label=f"Assumed Road dist (factor 1.28, median={np.median(dists_road):.2f} km)")

        ax.axvline(np.median(dists_straight), color=color, linestyle="--", linewidth=1.5)
        ax.axvline(np.median(dists_road), color="darkorange", linestyle=":", linewidth=1.5)

        ax.set_title(f"{city} Nearest-Neighbour Distance (n={len(gdf)})\n"
                     f"Coincident Pairs (d=0.0 km): {n_coincident} (Clean Network)", fontsize=10, fontweight="bold")
        ax.set_xlabel("Nearest-Neighbour Distance (km)", fontsize=9)
        ax.set_ylabel("Number of Stations", fontsize=9)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.5)

    fig.suptitle(
        "Gujarat Gas Station Nearest-Neighbour Spacing Distribution (High/Medium Confidence & Unique Coordinates)\n"
        "Buffer-Based Geographic Method — NOT an observed sales effect",
        fontsize=11, fontweight="bold", y=1.03
    )
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved histogram: {out_path}")


def plot_city_map(
    city: str,
    gdf_city: gpd.GeoDataFrame,
    city_comp: gpd.GeoDataFrame,
    city_raster: np.ndarray,
    win_transform: rasterio.Affine,
    out_path: str
):
    """
    Generate map showing Gujarat Gas stations, buffer-based catchments,
    WorldPop population raster surface, and competitor CNG stations.
    """
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)

    bounds_wgs84 = gdf_city.to_crs(WGS84_CRS).total_bounds
    pad = 0.08
    minx, miny, maxx, maxy = bounds_wgs84[0] - pad, bounds_wgs84[1] - pad, bounds_wgs84[2] + pad, bounds_wgs84[3] + pad

    with rasterio.open("data/raw/ind_ppp_2020_1km_UNadj.tif") as src:
        win = from_bounds(minx, miny, maxx, maxy, src.transform)
        crop_data = src.read(1, window=win)
        crop_extent = [minx, maxx, miny, maxy]

    crop_data = np.where(crop_data <= 0, np.nan, crop_data)
    im = ax.imshow(
        crop_data,
        extent=crop_extent,
        origin="upper",
        cmap="YlOrRd",
        alpha=0.55,
        interpolation="bilinear"
    )

    # Plot representative buffers: 2.0 km urban and 4.0 km corridor
    buf_4km = gpd.GeoSeries(gdf_city.geometry.buffer(4000.0), crs=PROJ_CRS).to_crs(WGS84_CRS)
    buf_2km = gpd.GeoSeries(gdf_city.geometry.buffer(2000.0), crs=PROJ_CRS).to_crs(WGS84_CRS)

    buf_4km.plot(ax=ax, facecolor="none", edgecolor="#2b8cbe", linewidth=0.8, linestyle="--", alpha=0.7)
    buf_2km.plot(ax=ax, facecolor="#7bccc4", edgecolor="#08589e", linewidth=1.1, alpha=0.25)

    gdf_city_wgs84 = gdf_city.to_crs(WGS84_CRS)
    ax.scatter(
        gdf_city_wgs84.geometry.x,
        gdf_city_wgs84.geometry.y,
        c="#084081",
        s=40,
        edgecolors="white",
        linewidths=0.8,
        zorder=5,
        label=f"Gujarat Gas Station (n={len(gdf_city)})"
    )

    if len(city_comp) > 0:
        comp_wgs84 = city_comp.to_crs(WGS84_CRS)
        ax.scatter(
            comp_wgs84.geometry.x,
            comp_wgs84.geometry.y,
            c="#d73027",
            s=75,
            marker="^",
            edgecolors="black",
            linewidths=0.9,
            zorder=6,
            label=f"Competitor Station (OSM, illustrative, n={len(city_comp)})"
        )
        for _, r in comp_wgs84.iterrows():
            brand_label = str(r.get("brand") or r.get("name") or "Competitor")
            if brand_label != "nan":
                ax.annotate(
                    f" {brand_label}",
                    (r.geometry.x, r.geometry.y),
                    fontsize=7.5,
                    fontweight="bold",
                    color="#99000d",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.85, ec="#d73027", lw=0.6)
                )

    ax.set_title(
        f"Gujarat Gas CNG Network Buffer-Based Catchments — {city}\n"
        "Buffer-Based Method (WorldPop 2020 UNadj) — NOT an observed sales effect",
        fontsize=11, fontweight="bold", pad=12
    )
    ax.set_xlabel("Longitude (°E)", fontsize=9)
    ax.set_ylabel("Latitude (°N)", fontsize=9)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("WorldPop 2020 Population / km²", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#084081", markeredgecolor="white", markersize=7, label=f"Gujarat Gas Stations (n={len(gdf_city)})"),
        mpatches.Patch(facecolor="#7bccc4", edgecolor="#08589e", alpha=0.4, label="2.0 km Urban Buffer Catchment"),
        mpatches.Patch(facecolor="none", edgecolor="#2b8cbe", linestyle="--", label="4.0 km Corridor Buffer Catchment"),
    ]
    if len(city_comp) > 0:
        legend_elements.append(
            Line2D([0], [0], marker="^", color="w", markerfacecolor="#d73027", markeredgecolor="black", markersize=8, label=f"Competitor CNG Station (OSM, illustrative, n={len(city_comp)})")
        )

    ax.legend(handles=legend_elements, loc="lower right", fontsize=8, framealpha=0.92, facecolor="white")
    ax.grid(True, linestyle=":", alpha=0.4, color="gray")

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved map: {out_path}")


def main():
    print("=" * 80)
    print("PS000002 MODULE C: BUFFER-BASED GEOGRAPHIC DEMAND-OVERLAP & SPACING ANALYSIS")
    print("=" * 80)
    print("Assumptions Documentation:")
    print("1. Road-network isolines could NOT be built because Overpass failed under rate limits.")
    print("2. Catchments are circular buffers (UTM Zone 43N).")
    print("3. Urban driving speed (25 km/h) and circuity factor (1.28, Ballou et al. 2002) are ASSUMPTIONS, not measurements.")
    print("4. Results represent geographic demand co-exposure (WorldPop 2020), NOT an observed sales drop.")
    print("=" * 80)

    # 1. Load clean data
    df_clean, df_comp, raster_path = load_clean_data()

    cities_to_analyze = ["Surat", "Rajkot"]
    all_pairs = []
    all_summaries = []
    curves_by_city = {}
    city_gdfs = {}
    competitor_exposure = {}

    for city in cities_to_analyze:
        city_df = df_clean[df_clean["city"] == city].copy().reset_index(drop=True)
        if len(city_df) == 0:
            print(f"Skipping {city}: no geocoded stations.")
            continue

        print(f"\n--- Analyzing {city} ({len(city_df)} clean stations) ---")
        gdf_city = gpd.GeoDataFrame(
            city_df,
            geometry=[Point(lon, lat) for lon, lat in zip(city_df["lon"], city_df["lat"])],
            crs=WGS84_CRS
        ).to_crs(PROJ_CRS)

        gdf_city = compute_nearest_neighbours(gdf_city)
        city_gdfs[city] = gdf_city

        city_raster, win_trans = extract_city_population_raster(raster_path, gdf_city)

        pairs_df, summary_df, curves_data, city_comp, comp_exp = analyze_city_multi_radius(
            city, gdf_city, city_raster, win_trans, df_comp
        )
        all_pairs.append(pairs_df)
        all_summaries.append(summary_df)
        curves_by_city[city] = curves_data
        competitor_exposure[city] = (len(city_comp), comp_exp[0], comp_exp[1])

        # Plot city map
        map_path = f"outputs/figures/{city.lower()}_stations_map.png"
        plot_city_map(city, gdf_city, city_comp, city_raster, win_trans, map_path)

    # Combine all pairwise results
    df_results = pd.concat(all_pairs, ignore_index=True)
    results_path = "data/processed/spacing_results.csv"
    df_results.to_csv(results_path, index=False)
    print(f"\nSaved pairwise spacing results: {results_path} ({len(df_results)} rows)")

    # Combine summary results
    df_summary = pd.concat(all_summaries, ignore_index=True)
    summary_path = "data/processed/spacing_summary.csv"
    df_summary.to_csv(summary_path, index=False)
    print(f"Saved spacing summary table: {summary_path}")

    print("\nSpacing Summary Table (Sensitivity to Assumed Radius R):")
    cols_display = [
        "city", "radius_km", "overlap_threshold_pct",
        "spacing_straight_km", "spacing_road_km", "multiple_k", "ci90_straight_km"
    ]
    print(df_summary[cols_display].to_string(index=False))

    # Nearest neighbour histogram
    nn_hist_path = "outputs/figures/nn_distance_hist.png"
    plot_nearest_neighbour_histogram(city_gdfs["Surat"], city_gdfs["Rajkot"], nn_hist_path)

    # Overlap vs distance for all radii on ONE figure
    ov_plot_path = "outputs/figures/overlap_vs_distance.png"
    plot_overlap_vs_distance_all_radii(curves_by_city, df_summary, ov_plot_path)

    # APPENDIX: Competitor analysis (illustrative)
    print("\n" + "=" * 80)
    print("APPENDIX: COMPETITOR ANALYSIS (illustrative: OSM contains very few competitor stations)")
    print("=" * 80)
    print("Notice: OpenStreetMap volunteer-mapped coverage is incomplete in Gujarat (~1% GGCL coverage).")
    print("Competitor proximity is presented purely for illustrative methodological completeness.")
    for city, (n_comp, exp_2, exp_6) in competitor_exposure.items():
        n_tot = len(city_gdfs[city])
        print(f"  {city}: {n_comp} OSM competitors mapped within 30 km.")
        print(f"    - {exp_2}/{n_tot} ({exp_2/n_tot*100:.1f}%) stations intersect competitor 2.0 km buffer.")
        print(f"    - {exp_6}/{n_tot} ({exp_6/n_tot*100:.1f}%) stations intersect competitor 6.0 km buffer.")
    print("=" * 80)

    print("\nBuffer-based spacing analysis completed successfully.")


if __name__ == "__main__":
    main()
