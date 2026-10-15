"""
src/spacing/catchment_overlap.py
--------------------------------
Geographic demand-overlap and station spacing analysis for Gujarat Gas Limited (PS000002, Module C).

IMPORTANT METHODOLOGICAL DISCLAIMER:
-------------------------------------
This module implements a purely GEOGRAPHIC DEMAND-OVERLAP method based on spatial
drive-time catchments and WorldPop population distribution. It is NOT a measured
sales drop and does NOT represent empirical station-level sales cannibalisation.
The overlap share reflects geographic demand co-exposure between station service areas.

Data Inputs:
- data/processed/stations_geocoded.csv: Geocoded Gujarat Gas stations.
- data/raw/osm_cng_stations_gujarat.csv: Competitor CNG stations from OpenStreetMap.
- data/raw/ind_ppp_2020_1km_UNadj.tif: WorldPop UN-adjusted population raster (2020, 1 km, CC BY 4.0).

Outputs:
- data/processed/spacing_results.csv: Pairwise straight-line and road distances with 5-min and 10-min overlap metrics.
- data/processed/spacing_summary.csv: Threshold distances at 30%, 20%, and 10% overlap sensitivity levels.
- outputs/figures/surat_stations_map.png: Map of Surat network, catchments, population density, and competitors.
- outputs/figures/rajkot_stations_map.png: Map of Rajkot network, catchments, population density, and competitors.
- outputs/figures/nn_distance_hist.png: Nearest-neighbour distance distributions.
- outputs/figures/overlap_vs_distance.png: Geographic demand-overlap decay curves and sensitivity ranges.
"""

import os
import math
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

# Urban network circuity factor: ratio of road network distance to straight-line Euclidean distance
# In Indian Tier-1/Tier-2 urban networks, empirical circuity is ~1.28 - 1.35 (Ballou et al.; Boscoe et al.)
CIRCUITY_FACTOR = 1.28

# Drive-time catchment parameters:
# Urban driving speed: 25 km/h
# 5-min catchment radius: 25 km/h * (5 / 60) h = 2.0833 km = 2083.33 m
# 10-min catchment radius: 25 km/h * (10 / 60) h = 4.1667 km = 4166.67 m
R_5MIN_METERS = 2083.33
R_10MIN_METERS = 4166.67

# Highway corridor parameters:
# Highway driving speed: 50 km/h
# 5-min highway catchment: 50 km/h * (5 / 60) h = 4.1667 km
# 10-min highway catchment: 50 km/h * (10 / 60) h = 8.3333 km

CITY_CENTRES = {
    "Surat": (21.1702, 72.8311),
    "Rajkot": (22.3039, 70.8022),
    "Ahmedabad": (23.0225, 72.5714),
    "Vadodara": (22.3072, 73.1812),
}


def load_data():
    """Load geocoded Gujarat Gas stations, competitor stations, and population raster."""
    geocoded_path = "data/processed/stations_geocoded.csv"
    osm_path = "data/raw/osm_cng_stations_gujarat.csv"
    raster_path = "data/raw/ind_ppp_2020_1km_UNadj.tif"

    if not os.path.exists(geocoded_path):
        raise FileNotFoundError(f"Missing geocoded stations: {geocoded_path}")
    if not os.path.exists(osm_path):
        raise FileNotFoundError(f"Missing OSM stations: {osm_path}")
    if not os.path.exists(raster_path):
        raise FileNotFoundError(f"Missing WorldPop population raster: {raster_path}")

    df_gg = pd.read_csv(geocoded_path)
    df_gg_valid = df_gg[df_gg["geocoded"] == True].copy()

    df_osm = pd.read_csv(osm_path)
    df_comp = df_osm[df_osm["cgd_company"] != "Gujarat Gas"].copy()

    return df_gg_valid, df_comp, raster_path


def compute_nearest_neighbours(gdf_city):
    """
    Compute straight-line and road nearest-neighbour distance for every station.
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


def extract_city_population_raster(raster_path, gdf_city):
    """
    Extract a cropped in-memory population array for the city's bounding area.
    """
    bounds = gdf_city.to_crs(WGS84_CRS).total_bounds
    # Add 0.15 deg (~15 km) padding
    minx, miny, maxx, maxy = bounds[0] - 0.15, bounds[1] - 0.15, bounds[2] + 0.15, bounds[3] + 0.15

    with rasterio.open(raster_path) as src:
        win = from_bounds(minx, miny, maxx, maxy, src.transform)
        arr = src.read(1, window=win)
        win_transform = src.window_transform(win)
        arr = np.where(arr < 0, 0, arr)  # Replace negative nodata with 0
        arr = np.nan_to_num(arr, nan=0.0)

    return arr, win_transform


def get_polygon_population(geom_4326, city_raster, win_transform):
    """Sum population pixels within a WGS84 polygon geometry."""
    if geom_4326.is_empty:
        return 0.0
    mask = geometry_mask([geom_4326], out_shape=city_raster.shape, transform=win_transform, invert=True)
    return float(np.sum(city_raster[mask]))


def analyze_city_spacing(city, gdf_city, city_raster, win_transform, df_comp):
    """
    Run spacing, catchment overlaps, and competitor interactions for a single city.
    """
    n = len(gdf_city)
    city_clat, city_clon = CITY_CENTRES.get(city, (gdf_city["lat"].mean(), gdf_city["lon"].mean()))

    # Build metric buffers in UTM 43N
    buf_5_m = gdf_city.geometry.buffer(R_5MIN_METERS)
    buf_10_m = gdf_city.geometry.buffer(R_10MIN_METERS)

    # Convert buffers to WGS84 for raster sampling
    buf_5_4326 = gpd.GeoSeries(buf_5_m, crs=PROJ_CRS).to_crs(WGS84_CRS)
    buf_10_4326 = gpd.GeoSeries(buf_10_m, crs=PROJ_CRS).to_crs(WGS84_CRS)

    # Compute individual station demand
    demand_5 = [get_polygon_population(g, city_raster, win_transform) for g in buf_5_4326]
    demand_10 = [get_polygon_population(g, city_raster, win_transform) for g in buf_10_4326]

    gdf_city["demand_5min"] = demand_5
    gdf_city["demand_10min"] = demand_10

    # Pairwise overlaps
    pair_rows = []
    for i in range(n):
        for j in range(i + 1, n):
            d_straight = gdf_city.geometry.iloc[i].distance(gdf_city.geometry.iloc[j]) / 1000.0
            d_road = d_straight * CIRCUITY_FACTOR

            # 5-min catchment overlap
            ov_pop_5 = 0.0
            ov_share_5 = 0.0
            if d_straight * 1000.0 < 2 * R_5MIN_METERS:
                inter_5 = buf_5_m.iloc[i].intersection(buf_5_m.iloc[j])
                if not inter_5.is_empty:
                    inter_5_4326 = gpd.GeoSeries([inter_5], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
                    ov_pop_5 = get_polygon_population(inter_5_4326, city_raster, win_transform)
                    min_dem_5 = min(demand_5[i], demand_5[j])
                    ov_share_5 = ov_pop_5 / min_dem_5 if min_dem_5 > 0 else 0.0

            # 10-min catchment overlap
            ov_pop_10 = 0.0
            ov_share_10 = 0.0
            if d_straight * 1000.0 < 2 * R_10MIN_METERS:
                inter_10 = buf_10_m.iloc[i].intersection(buf_10_m.iloc[j])
                if not inter_10.is_empty:
                    inter_10_4326 = gpd.GeoSeries([inter_10], crs=PROJ_CRS).to_crs(WGS84_CRS).iloc[0]
                    ov_pop_10 = get_polygon_population(inter_10_4326, city_raster, win_transform)
                    min_dem_10 = min(demand_10[i], demand_10[j])
                    ov_share_10 = ov_pop_10 / min_dem_10 if min_dem_10 > 0 else 0.0

            pair_rows.append({
                "city": city,
                "station_a": gdf_city.loc[i, "station_name"],
                "station_b": gdf_city.loc[j, "station_name"],
                "distance_straight_km": round(d_straight, 3),
                "distance_road_km": round(d_road, 3),
                "overlap_share_5min": round(min(1.0, ov_share_5), 4),
                "overlap_demand_5min": round(ov_pop_5, 1),
                "overlap_share_10min": round(min(1.0, ov_share_10), 4),
                "overlap_demand_10min": round(ov_pop_10, 1),
            })

    # Competitor interaction
    p_center = Point(city_clon, city_clat)
    gdf_center = gpd.GeoDataFrame(geometry=[p_center], crs=WGS84_CRS).to_crs(PROJ_CRS)
    c_pt = gdf_center.geometry.iloc[0]

    gdf_comp_m = gpd.GeoDataFrame(
        df_comp,
        geometry=[Point(lon, lat) for lon, lat in zip(df_comp["lon"], df_comp["lat"])],
        crs=WGS84_CRS
    ).to_crs(PROJ_CRS)

    gdf_comp_m["dist_center_km"] = [g.distance(c_pt) / 1000.0 for g in gdf_comp_m.geometry]
    city_comp = gdf_comp_m[gdf_comp_m["dist_center_km"] <= 30].copy().reset_index(drop=True)

    comp_exp_5 = 0
    comp_exp_10 = 0
    if len(city_comp) > 0:
        c_buf_5 = city_comp.geometry.buffer(R_5MIN_METERS)
        c_buf_10 = city_comp.geometry.buffer(R_10MIN_METERS)
        for i in range(n):
            if any(buf_5_m.iloc[i].intersects(c_buf_5.iloc[k]) for k in range(len(city_comp))):
                comp_exp_5 += 1
            if any(buf_10_m.iloc[i].intersects(c_buf_10.iloc[k]) for k in range(len(city_comp))):
                comp_exp_10 += 1

    return pd.DataFrame(pair_rows), city_comp, (comp_exp_5, comp_exp_10)


def calculate_sensitivity_thresholds(df_pairs, city, catchment_min):
    """
    Calculate distance thresholds at which average demand-overlap falls below 30%, 20%, and 10%.
    """
    col = f"overlap_share_{catchment_min}min"
    r_max = 2 * (R_5MIN_METERS / 1000.0 if catchment_min == 5 else R_10MIN_METERS / 1000.0)

    sub = df_pairs[(df_pairs["city"] == city) & (df_pairs["distance_straight_km"] <= r_max)].copy()
    bins = np.linspace(0, r_max, 25)
    sub["bin"] = pd.cut(sub["distance_straight_km"], bins)

    binned = sub.groupby("bin", observed=False).agg(
        dist_mean=("distance_straight_km", "mean"),
        overlap_mean=(col, "mean"),
        count=(col, "count")
    ).dropna()

    thresholds = {}
    for th in [0.30, 0.20, 0.10]:
        below = binned[binned["overlap_mean"] < th]
        if not below.empty:
            idx = below.index[0]
            loc = binned.index.get_loc(idx)
            if loc > 0:
                prev = binned.iloc[loc - 1]
                curr = binned.iloc[loc]
                if curr["overlap_mean"] != prev["overlap_mean"]:
                    d_cross = prev["dist_mean"] + (th - prev["overlap_mean"]) * (curr["dist_mean"] - prev["dist_mean"]) / (curr["overlap_mean"] - prev["overlap_mean"])
                else:
                    d_cross = curr["dist_mean"]
            else:
                d_cross = below.iloc[0]["dist_mean"]
            d_cross = max(0.1, min(r_max, d_cross))
        else:
            d_cross = r_max

        thresholds[th] = {
            "straight_km": round(float(d_cross), 2),
            "road_km": round(float(d_cross * CIRCUITY_FACTOR), 2),
        }

    return thresholds


def plot_city_map(city, gdf_city, city_comp, city_raster, win_transform, out_path):
    """
    Generate high-resolution map showing Gujarat Gas stations, catchments,
    WorldPop population raster surface, and competitor CNG stations.
    """
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)

    # Plot WorldPop density surface as background image
    bounds_wgs84 = gdf_city.to_crs(WGS84_CRS).total_bounds
    pad = 0.08
    minx, miny, maxx, maxy = bounds_wgs84[0] - pad, bounds_wgs84[1] - pad, bounds_wgs84[2] + pad, bounds_wgs84[3] + pad

    # Re-crop raster to exact plot bounds
    with rasterio.open("data/raw/ind_ppp_2020_1km_UNadj.tif") as src:
        win = from_bounds(minx, miny, maxx, maxy, src.transform)
        crop_data = src.read(1, window=win)
        crop_trans = src.window_transform(win)
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

    # Plot catchments in WGS84
    buf_10_4326 = gpd.GeoSeries(gdf_city.geometry.buffer(R_10MIN_METERS), crs=PROJ_CRS).to_crs(WGS84_CRS)
    buf_5_4326 = gpd.GeoSeries(gdf_city.geometry.buffer(R_5MIN_METERS), crs=PROJ_CRS).to_crs(WGS84_CRS)

    buf_10_4326.plot(ax=ax, facecolor="none", edgecolor="#2b8cbe", linewidth=0.8, linestyle="--", alpha=0.7)
    buf_5_4326.plot(ax=ax, facecolor="#7bccc4", edgecolor="#08589e", linewidth=1.1, alpha=0.25)

    # Plot Gujarat Gas station points
    gdf_city_wgs84 = gdf_city.to_crs(WGS84_CRS)
    ax.scatter(
        gdf_city_wgs84.geometry.x,
        gdf_city_wgs84.geometry.y,
        c="#084081",
        s=36,
        edgecolors="white",
        linewidths=0.7,
        zorder=5,
        label=f"Gujarat Gas Station (n={len(gdf_city)})"
    )

    # Plot Competitor stations if present
    if len(city_comp) > 0:
        comp_wgs84 = city_comp.to_crs(WGS84_CRS)
        ax.scatter(
            comp_wgs84.geometry.x,
            comp_wgs84.geometry.y,
            c="#d73027",
            s=80,
            marker="^",
            edgecolors="black",
            linewidths=1.0,
            zorder=6,
            label=f"Competitor CNG Station (n={len(city_comp)})"
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

    # Styling
    ax.set_title(f"Gujarat Gas CNG Network Catchment Overlap — {city}\n"
                 r"$\bf{Geographic\ Demand-Overlap\ Method\ (WorldPop\ 2020\ UNadj)\ -\ NOT\ an\ observed\ sales\ drop}$",
                 fontsize=11, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude (°E)", fontsize=9)
    ax.set_ylabel("Latitude (°N)", fontsize=9)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    cbar = plt.colorbar(im, ax=ax, fraction=0.035, pad=0.04)
    cbar.set_label("WorldPop 2020 Population / km²", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    # Custom legend
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#084081", markeredgecolor="white", markersize=7, label=f"Gujarat Gas Stations (n={len(gdf_city)})"),
        mpatches.Patch(facecolor="#7bccc4", edgecolor="#08589e", alpha=0.4, label="5-min Drive Catchment (~2.1 km at 25 km/h)"),
        mpatches.Patch(facecolor="none", edgecolor="#2b8cbe", linestyle="--", label="10-min Drive Catchment (~4.2 km at 25 km/h)"),
    ]
    if len(city_comp) > 0:
        legend_elements.append(Line2D([0], [0], marker="^", color="w", markerfacecolor="#d73027", markeredgecolor="black", markersize=9, label=f"Competitor CNG Stations (n={len(city_comp)})"))

    ax.legend(handles=legend_elements, loc="lower right", fontsize=8, framealpha=0.92, facecolor="white")
    ax.grid(True, linestyle=":", alpha=0.4, color="gray")

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved map: {out_path}")


def plot_nearest_neighbour_histogram(gdf_surat, gdf_rajkot, out_path):
    """
    Plot nearest-neighbour distance distributions for Surat and Rajkot.
    """
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=300)

    for ax, gdf, city, color in zip(axes, [gdf_surat, gdf_rajkot], ["Surat", "Rajkot"], ["#1f78b4", "#33a02c"]):
        dists_straight = gdf["nn_straight_km"]
        dists_road = gdf["nn_road_km"]

        # Number of coincident stations
        n_coincident = sum(1 for d in dists_straight if d == 0.0)

        # Non-zero distances for distribution shape
        bins = np.linspace(0, max(12, math.ceil(dists_road.max())), 25)

        ax.hist(dists_straight, bins=bins, alpha=0.65, color=color, edgecolor="black", label=f"Straight-line (median={np.median(dists_straight):.2f} km)")
        ax.hist(dists_road, bins=bins, alpha=0.45, color="orange", edgecolor="darkorange", linestyle="--", label=f"Road dist (tau=1.28, median={np.median(dists_road):.2f} km)")

        ax.axvline(np.median(dists_straight), color=color, linestyle="--", linewidth=1.5)
        ax.axvline(np.median(dists_road), color="darkorange", linestyle=":", linewidth=1.5)

        ax.set_title(f"{city} Nearest-Neighbour Distance (n={len(gdf)})\n"
                     f"Coincident/Pincode Centroid Pairs (d=0.0 km): {n_coincident}", fontsize=10, fontweight="bold")
        ax.set_xlabel("Nearest-Neighbour Distance (km)", fontsize=9)
        ax.set_ylabel("Number of Stations", fontsize=9)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.5)

    fig.suptitle("Gujarat Gas Station Nearest-Neighbour Spacing Distribution\n"
                 r"$\bf{Geographic\ demand-overlap\ method\ -\ NOT\ an\ observed\ sales\ drop}$",
                 fontsize=11, fontweight="bold", y=1.03)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved histogram: {out_path}")


def plot_overlap_vs_distance(df_results, summary_df, out_path):
    """
    Plot geographic demand-overlap share vs station-to-station distance
    with 30%, 20%, and 10% sensitivity thresholds.
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)

    for ax, city, color_base in zip(axes, ["Surat", "Rajkot"], ["#08519c", "#006d2c"]):
        city_pairs = df_results[df_results["city"] == city].copy()

        # 5-min catchment scatter & fit
        sub_5 = city_pairs[city_pairs["distance_straight_km"] <= 2 * (R_5MIN_METERS / 1000.0)]
        ax.scatter(
            sub_5["distance_straight_km"],
            sub_5["overlap_share_5min"] * 100.0,
            alpha=0.25,
            s=18,
            color="#3182bd",
            label="5-min Catchment Pairs (~2.1 km radius)"
        )

        # 10-min catchment scatter & fit
        sub_10 = city_pairs[city_pairs["distance_straight_km"] <= 2 * (R_10MIN_METERS / 1000.0)]
        ax.scatter(
            sub_10["distance_straight_km"],
            sub_10["overlap_share_10min"] * 100.0,
            alpha=0.18,
            s=14,
            color="#e6550d",
            label="10-min Catchment Pairs (~4.2 km radius)"
        )

        # Binned average curve for 5-min
        bins_5 = np.linspace(0, 2 * (R_5MIN_METERS / 1000.0), 16)
        sub_5_copy = sub_5.copy()
        sub_5_copy["bin"] = pd.cut(sub_5_copy["distance_straight_km"], bins_5)
        curve_5 = sub_5_copy.groupby("bin", observed=False).agg(
            dist=("distance_straight_km", "mean"),
            ov=("overlap_share_5min", "mean")
        ).dropna()
        ax.plot(curve_5["dist"], curve_5["ov"] * 100.0, color="#08519c", linewidth=2.2, label="5-min Mean Overlap Trend")

        # Binned average curve for 10-min
        bins_10 = np.linspace(0, 2 * (R_10MIN_METERS / 1000.0), 20)
        sub_10_copy = sub_10.copy()
        sub_10_copy["bin"] = pd.cut(sub_10_copy["distance_straight_km"], bins_10)
        curve_10 = sub_10_copy.groupby("bin", observed=False).agg(
            dist=("distance_straight_km", "mean"),
            ov=("overlap_share_10min", "mean")
        ).dropna()
        ax.plot(curve_10["dist"], curve_10["ov"] * 100.0, color="#a63603", linewidth=2.2, linestyle="--", label="10-min Mean Overlap Trend")

        # Threshold lines (30%, 20%, 10%)
        ax.axhline(30, color="#636363", linestyle=":", linewidth=1.0, alpha=0.7)
        ax.axhline(20, color="#636363", linestyle="--", linewidth=1.0, alpha=0.7)
        ax.axhline(10, color="#636363", linestyle="-.", linewidth=1.0, alpha=0.7)

        # Annotate thresholds from summary_df
        c_sum_5 = summary_df[(summary_df["city"] == city) & (summary_df["catchment_minutes"] == 5)]
        th_30 = c_sum_5[c_sum_5["overlap_threshold_pct"] == 30]["distance_straight_km"].values
        th_10 = c_sum_5[c_sum_5["overlap_threshold_pct"] == 10]["distance_straight_km"].values
        d30_str = f"{th_30[0]:.2f}" if len(th_30) > 0 else "N/A"
        d10_str = f"{th_10[0]:.2f}" if len(th_10) > 0 else "N/A"

        ax.text(
            0.96, 0.94,
            f"5-min Sensitivity Range (30% to 10% overlap):\n{d30_str} km to {d10_str} km straight-line",
            transform=ax.transAxes,
            fontsize=8,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#08519c", alpha=0.9)
        )

        ax.set_title(f"{city}: Demand Overlap vs Station Distance", fontsize=10, fontweight="bold")
        ax.set_xlabel("Station-to-Station Straight-Line Distance (km)", fontsize=9)
        ax.set_ylabel("Demand Overlap Share (%)", fontsize=9)
        ax.set_ylim(-2, 105)
        ax.set_xlim(0, 9.0)
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.legend(loc="lower left", fontsize=7.5)

    fig.suptitle("Demand-Weighted Catchment Overlap Share vs Station Distance\n"
                 r"$\bf{Geographic\ demand-overlap\ method\ (WorldPop\ 2020)\ -\ NOT\ an\ observed\ sales\ drop}$",
                 fontsize=11, fontweight="bold", y=1.03)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved overlap vs distance plot: {out_path}")


def main():
    print("=" * 70)
    print("PS000002 MODULE C: GEOGRAPHIC DEMAND-OVERLAP & SPACING ANALYSIS")
    print("=" * 70)

    # 1. Load data
    df_gg_valid, df_comp, raster_path = load_data()
    print(f"Loaded {len(df_gg_valid)} valid geocoded Gujarat Gas stations.")
    print(f"Loaded {len(df_comp)} competitor stations across Gujarat.")

    cities_to_analyze = ["Surat", "Rajkot"]
    all_pairs = []
    summary_rows = []
    city_gdfs = {}
    competitor_exposure = {}

    for city in cities_to_analyze:
        city_df = df_gg_valid[df_gg_valid["city"] == city].copy().reset_index(drop=True)
        if len(city_df) == 0:
            print(f"Skipping {city}: no geocoded stations.")
            continue

        print(f"\n--- Analyzing {city} ({len(city_df)} stations) ---")
        gdf_city = gpd.GeoDataFrame(
            city_df,
            geometry=[Point(lon, lat) for lon, lat in zip(city_df["lon"], city_df["lat"])],
            crs=WGS84_CRS
        ).to_crs(PROJ_CRS)

        # Nearest neighbour calculation
        gdf_city = compute_nearest_neighbours(gdf_city)
        city_gdfs[city] = gdf_city

        # Extract raster window
        city_raster, win_transform = extract_city_population_raster(raster_path, gdf_city)

        # Spacing and overlap
        pairs_df, city_comp, comp_exp = analyze_city_spacing(
            city, gdf_city, city_raster, win_transform, df_comp
        )
        all_pairs.append(pairs_df)
        competitor_exposure[city] = (len(city_comp), comp_exp[0], comp_exp[1])

        # Compute sensitivity thresholds
        for c_min in [5, 10]:
            th_dict = calculate_sensitivity_thresholds(pairs_df, city, c_min)
            for th_pct, dists in th_dict.items():
                summary_rows.append({
                    "city": city,
                    "catchment_minutes": c_min,
                    "overlap_threshold_pct": int(th_pct * 100),
                    "distance_straight_km": dists["straight_km"],
                    "distance_road_km": dists["road_km"],
                })

        # Plot map
        map_path = f"outputs/figures/{city.lower()}_stations_map.png"
        plot_city_map(city, gdf_city, city_comp, city_raster, win_transform, map_path)

    # Combine all pair results
    df_results = pd.concat(all_pairs, ignore_index=True)
    results_path = "data/processed/spacing_results.csv"
    df_results.to_csv(results_path, index=False)
    print(f"\nSaved pairwise spacing results: {results_path} ({len(df_results)} rows)")

    # Combine summary results
    df_summary = pd.DataFrame(summary_rows)
    summary_path = "data/processed/spacing_summary.csv"
    df_summary.to_csv(summary_path, index=False)
    print(f"Saved spacing summary table: {summary_path}")
    print("\nSpacing Summary Table:")
    print(df_summary.to_string(index=False))

    # Plot nearest-neighbour histogram
    nn_hist_path = "outputs/figures/nn_distance_hist.png"
    plot_nearest_neighbour_histogram(city_gdfs["Surat"], city_gdfs["Rajkot"], nn_hist_path)

    # Plot overlap vs distance
    ov_plot_path = "outputs/figures/overlap_vs_distance.png"
    plot_overlap_vs_distance(df_results, df_summary, ov_plot_path)

    # Competitor impact summary
    print("\nCompetitor Presence & Exposure Summary:")
    for city, (n_comp, exp_5, exp_10) in competitor_exposure.items():
        n_tot = len(city_gdfs[city])
        print(f"  {city}: {n_comp} competitors within 30 km.")
        print(f"    {exp_5}/{n_tot} ({exp_5/n_tot*100:.1f}%) GG stations share 5-min catchment demand with competitors.")
        print(f"    {exp_10}/{n_tot} ({exp_10/n_tot*100:.1f}%) GG stations share 10-min catchment demand with competitors.")

    print("\nSpacing analysis completed successfully.")


if __name__ == "__main__":
    main()
