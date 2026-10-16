"""Module D (Part 2): EV Scenario Modeling and Siting Robustness (PS000002).

Audited and hardened implementation (Task 4b):
- Normalised multipliers: Multiplier equals 1.0000 in 2026 (divided by 2026 value)
  so all scenarios start identically from the observed Q1 FY27 annualized volume (3.76 mmscmd).
- SOURCED vs ASSUMPTION:
  * NITI Aayog target quoted exactly with page citation.
  * Clarified that NITI Aayog 2030 targets are SALES-SHARE targets.
  * Converted to ON-ROAD FLEET SHARES using vehicle stock turnover assumptions (ASSUMPTION).
- Robustness wording updated:
  * "ROBUST" renamed to "keeps top-10 rank under the assumed density rule".
  * Base rank (without density bonus) and scenario rank (with density bonus) both reported.
- Siting evaluation integrated with the audited municipal candidate grid from rank_sites.py.
"""

import argparse
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.windows import from_bounds
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# SOURCED CITATIONS AND PARAMETER METADATA
# Source: NITI Aayog & Rocky Mountain Institute (RMI) 2021 report:
# "Mobilising Electric Vehicle Financing in India", URL: https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf
# - Executive Summary / p. 12:
#   "The transition to electric vehicles (EVs) in India is targeted to reach 80% sales penetration for two- and three-wheelers, 70% for commercial cars, 40% for buses, and 30% for private cars by 2030."
# IMPORTANT DISTINCTION:
# NITI Aayog targets are SALES-SHARE targets (proportion of new vehicle sales in 2030).
# CNG displacement depends on CUMULATIVE ON-ROAD FLEET SHARE (vehicle stock).
# We convert sales targets to fleet share ceilings using typical Indian stock turnover lifetimes (ASSUMPTION).

SCENARIO_METADATA = {
    "Low EV": {
        "description": "Slow transition constrained by charging bottlenecks, financing friction, and high battery replacement costs.",
        "3W": {
            "sales_target_2030": 0.50, "source_sales": "ASSUMPTION: Sluggish 3W adoption",
            "fleet_ceiling_L": 0.35, "source_L": "ASSUMPTION: 35% on-road fleet share with 8-yr turnover",
            "steepness_k": 0.40, "source_k": "ASSUMPTION",
            "midpoint_t0": 2030, "source_t0": "ASSUMPTION"
        },
        "4W": {
            "sales_target_2030": 0.25, "source_sales": "ASSUMPTION: Slow car electrification outside top metros",
            "fleet_ceiling_L": 0.15, "source_L": "ASSUMPTION: 15% on-road fleet share with 10-yr turnover",
            "steepness_k": 0.35, "source_k": "ASSUMPTION",
            "midpoint_t0": 2032, "source_t0": "ASSUMPTION"
        },
        "Bus": {
            "sales_target_2030": 0.25, "source_sales": "ASSUMPTION: Subdued municipal e-bus procurement",
            "fleet_ceiling_L": 0.18, "source_L": "ASSUMPTION: 18% on-road bus fleet with 12-yr replacement",
            "steepness_k": 0.35, "source_k": "ASSUMPTION",
            "midpoint_t0": 2031, "source_t0": "ASSUMPTION"
        },
    },
    "Medium EV": {
        "description": "Baseline policy transition aligned with NITI Aayog (2021) 2030 national targets and Gujarat EV Policy incentives.",
        "3W": {
            "sales_target_2030": 0.80, "source_sales": "SOURCED: NITI Aayog (2021) p. 12 ('80% sales penetration for two- and three-wheelers by 2030')",
            "url_sales": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
            "fleet_ceiling_L": 0.55, "source_L": "ASSUMPTION: 55% on-road fleet ceiling derived from 80% sales target lagged across 8-yr operational lifetime",
            "steepness_k": 0.45, "source_k": "ASSUMPTION: Logistic diffusion rate",
            "midpoint_t0": 2029, "source_t0": "ASSUMPTION: Fleet inflection year based on TCO parity"
        },
        "4W": {
            "sales_target_2030": 0.40, "source_sales": "SOURCED: NITI Aayog (2021) p. 12 (70% commercial cabs, 30% private cars -> ~40% composite 4W sales target)",
            "url_sales": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
            "fleet_ceiling_L": 0.25, "source_L": "ASSUMPTION: 25% on-road car/taxi fleet ceiling derived from 40% sales target with 10-yr turnover",
            "steepness_k": 0.40, "source_k": "ASSUMPTION",
            "midpoint_t0": 2030, "source_t0": "ASSUMPTION"
        },
        "Bus": {
            "sales_target_2030": 0.40, "source_sales": "SOURCED: NITI Aayog (2021) p. 12 ('40% for buses by 2030')",
            "url_sales": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
            "fleet_ceiling_L": 0.28, "source_L": "ASSUMPTION: 28% on-road bus fleet ceiling derived from 40% sales target with 12-yr municipal bus life",
            "steepness_k": 0.40, "source_k": "ASSUMPTION",
            "midpoint_t0": 2029, "source_t0": "ASSUMPTION"
        },
    },
    "High EV": {
        "description": "Aggressive disruption with rapid TCO parity, PM-eBus Sewa mandate, and urban municipal ICE restrictions.",
        "3W": {
            "sales_target_2030": 0.95, "source_sales": "ASSUMPTION: Near-complete 3W electrification mandate",
            "fleet_ceiling_L": 0.70, "source_L": "ASSUMPTION: 70% on-road fleet ceiling with accelerated vehicle scrappage",
            "steepness_k": 0.55, "source_k": "ASSUMPTION",
            "midpoint_t0": 2028, "source_t0": "ASSUMPTION"
        },
        "4W": {
            "sales_target_2030": 0.60, "source_sales": "ASSUMPTION: 100% app-cab electrification + 40% private cars",
            "fleet_ceiling_L": 0.40, "source_L": "ASSUMPTION: 40% on-road fleet ceiling with rapid commercial turnover",
            "steepness_k": 0.45, "source_k": "ASSUMPTION",
            "midpoint_t0": 2029, "source_t0": "ASSUMPTION"
        },
        "Bus": {
            "sales_target_2030": 0.75, "source_sales": "ASSUMPTION: 100% municipal city bus + 50% intercity e-buses",
            "fleet_ceiling_L": 0.45, "source_L": "ASSUMPTION: 45% on-road bus fleet ceiling with accelerated transit phase-out",
            "steepness_k": 0.50, "source_k": "ASSUMPTION",
            "midpoint_t0": 2028, "source_t0": "ASSUMPTION"
        },
    }
}

# Segment share in CNG consumption (ASSUMPTION based on Gujarat CGD fleet profile)
SEGMENT_WEIGHTS = {
    "3W": 0.50,   # ASSUMPTION: 50% of retail CNG volume
    "4W": 0.35,   # ASSUMPTION: 35% of retail CNG volume
    "Bus": 0.15   # ASSUMPTION: 15% of retail CNG volume
}

# Baseline volume: Q1 FY27 annualized sales = 3.760 mmscmd (SOURCED from quarterly_master.csv)
BASE_YEAR = 2026
BASE_VOLUME_MMSCMD = 3.760
COUNTERFACTUAL_CAGR = 0.04  # ASSUMPTION: 4.0% p.a. organic ICE volume growth without EV substitution


def logistic_s_curve(t, L, k, t0):
    """Logistic S-curve formula: S(t) = L / (1 + exp(-k * (t - t0)))."""
    return L / (1.0 + np.exp(-k * (t - t0)))


def build_normalized_ev_scenarios(years=range(2026, 2036)):
    """Generate annual EV adoption shares and NORMALIZED CNG demand multipliers.

    NORMALIZATION RULE:
    Multiplier is normalized so that it identically equals 1.0000 in 2026 (divided by 2026 raw value).
    This guarantees that all scenarios start from the exact observed Q1 FY27 actual volume of 3.760 mmscmd.
    """
    rows = []
    for sc_name, params in SCENARIO_METADATA.items():
        # First compute raw multipliers across all years
        raw_fleet_shares = {}
        raw_multipliers = {}
        shares_3w = {}
        shares_4w = {}
        shares_bus = {}

        for yr in years:
            s_3w = float(logistic_s_curve(yr, params["3W"]["fleet_ceiling_L"], params["3W"]["steepness_k"], params["3W"]["midpoint_t0"]))
            s_4w = float(logistic_s_curve(yr, params["4W"]["fleet_ceiling_L"], params["4W"]["steepness_k"], params["4W"]["midpoint_t0"]))
            s_bus = float(logistic_s_curve(yr, params["Bus"]["fleet_ceiling_L"], params["Bus"]["steepness_k"], params["Bus"]["midpoint_t0"]))

            ev_fleet_share = (
                SEGMENT_WEIGHTS["3W"] * s_3w
                + SEGMENT_WEIGHTS["4W"] * s_4w
                + SEGMENT_WEIGHTS["Bus"] * s_bus
            )
            raw_m = 1.0 - ev_fleet_share

            shares_3w[yr] = s_3w
            shares_4w[yr] = s_4w
            shares_bus[yr] = s_bus
            raw_fleet_shares[yr] = ev_fleet_share
            raw_multipliers[yr] = raw_m

        # Multiplier in base year 2026
        m_2026 = raw_multipliers[BASE_YEAR]

        for yr in years:
            norm_multiplier = raw_multipliers[yr] / m_2026  # Normalized so 2026 == 1.0000
            cf_demand = BASE_VOLUME_MMSCMD * ((1.0 + COUNTERFACTUAL_CAGR) ** (yr - BASE_YEAR))
            proj_demand = cf_demand * norm_multiplier

            rows.append({
                "year": yr,
                "scenario": sc_name,
                "ev_fleet_share_3w": round(shares_3w[yr], 4),
                "ev_fleet_share_4w": round(shares_4w[yr], 4),
                "ev_fleet_share_bus": round(shares_bus[yr], 4),
                "ev_fleet_share": round(raw_fleet_shares[yr], 4),
                "raw_cng_multiplier": round(raw_multipliers[yr], 4),
                "cng_demand_multiplier": round(norm_multiplier, 4),
                "counterfactual_demand_mmscmd": round(cf_demand, 3),
                "projected_cng_demand_mmscmd": round(proj_demand, 3)
            })

    return pd.DataFrame(rows)


def plot_ev_scenarios(df_scenarios, output_png_path="outputs/figures/ev_scenarios.png"):
    """Plot publication-quality 3-panel figure with normalized multipliers and demand projections."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), dpi=300)

    colors = {
        "Low EV": "#2ca02c",
        "Medium EV": "#ff7f0e",
        "High EV": "#d62728"
    }

    # Panel 1: S-Curve EV Fleet Share
    ax1 = axes[0]
    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax1.plot(sub["year"], sub["ev_fleet_share"] * 100, label=f"{sc_name} (Composite)", color=colors[sc_name], linewidth=2.5)
        if sc_name == "Medium EV":
            ax1.plot(sub["year"], sub["ev_fleet_share_3w"] * 100, color=colors[sc_name], linestyle=":", alpha=0.75, label="Medium EV (3W Fleet)")
            ax1.plot(sub["year"], sub["ev_fleet_share_4w"] * 100, color=colors[sc_name], linestyle="--", alpha=0.75, label="Medium EV (4W Fleet)")
            ax1.plot(sub["year"], sub["ev_fleet_share_bus"] * 100, color=colors[sc_name], linestyle="-.", alpha=0.75, label="Medium EV (Bus Fleet)")

    ax1.set_title("A. EV Fleet Adoption S-Curves by Segment\n(Lagged from NITI Aayog Sales Targets [ASSUMPTION])", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Year", fontsize=10)
    ax1.set_ylabel("On-Road EV Fleet Share (%)", fontsize=10)
    ax1.set_ylim(0, 65)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.9)

    # Panel 2: Normalized CNG Multiplier
    ax2 = axes[1]
    ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1.5, label="2026 Observed Baseline (Index 1.00)")
    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax2.plot(sub["year"], sub["cng_demand_multiplier"], marker="o", markersize=4, label=f"{sc_name} (Normalized)", color=colors[sc_name], linewidth=2.2)

    ax2.set_title("B. Normalized CNG Demand Multiplier\n(All Scenarios Normalized to 1.00 in 2026)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Year", fontsize=10)
    ax2.set_ylabel("Normalized CNG Multiplier", fontsize=10)
    ax2.set_ylim(0.50, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.9)

    # Panel 3: GGCL Network CNG Demand
    ax3 = axes[2]
    sub_med = df_scenarios[df_scenarios["scenario"] == "Medium EV"]
    ax3.plot(sub_med["year"], sub_med["counterfactual_demand_mmscmd"], color="black", linestyle="--", linewidth=2.0, label="Counterfactual ICE (4% CAGR)")

    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax3.plot(sub["year"], sub["projected_cng_demand_mmscmd"], marker="s", markersize=4, label=f"Projected: {sc_name}", color=colors[sc_name], linewidth=2.2)

    sub_high = df_scenarios[df_scenarios["scenario"] == "High EV"]
    ax3.fill_between(
        sub_med["year"],
        sub_high["projected_cng_demand_mmscmd"],
        sub_med["counterfactual_demand_mmscmd"],
        color="red",
        alpha=0.10,
        label="EV Demand Destruction Gap"
    )

    ax3.set_title("C. Network CNG Demand Trajectory\n(Base: 3.760 mmscmd Q1 FY27 Actual [SOURCED])", fontsize=11, fontweight="bold")
    ax3.set_xlabel("Year", fontsize=10)
    ax3.set_ylabel("Network CNG Sales (mmscmd)", fontsize=10)
    ax3.set_ylim(2.5, 6.0)
    ax3.grid(True, linestyle=":", alpha=0.6)
    ax3.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path, dpi=300)
    plt.close()
    print(f"  [Figure] Saved updated EV scenario figure to {output_png_path}")


def evaluate_siting_robustness(stations_file="data/processed/stations_geocoded.csv", raster_file="data/raw/ind_ppp_2020_1km_UNadj.tif"):
    """Evaluate candidate site ranking with and without density bonus under EV scenarios.

    RULE DEFINITION (Urban Density Fleet Resilience Rule [ASSUMPTION]):
    As statewide EV adoption increases, peripheral retail CNG demand contracts faster as personal
    vehicles electrify. In contrast, dense core corridors retain commercial fleet activity
    (auto-rickshaws, shared cabs) due to high vehicle utilization and lack of depot charging space.
    Under scenario s with multiplier M_s:
        Score_{i, s} = Score_{i, base} * [1.0 + gamma_s * Z_{density, i}]
    where gamma_base = 0.0, gamma_Low = 0.10, gamma_Medium = 0.25, gamma_High = 0.40.

    TERMINOLOGY (Task 4b):
    - Sites remaining in Top 10 across all 3 EV scenarios are labeled:
      "keeps top-10 rank under the assumed density rule".
    - Base rank (without density bonus) and scenario ranks are reported side-by-side for comparison.
    """
    try:
        from src.siting.rank_sites import (
            load_and_classify_stations,
            build_municipal_candidate_grid,
            score_candidate_sites,
            MUNICIPAL_BOUNDS,
            DEFAULT_MIN_SPACING_KM,
            DEFAULT_POP_THRESHOLD,
            DEFAULT_CATCHMENT_RADIUS_M
        )
    except ImportError:
        from rank_sites import (
            load_and_classify_stations,
            build_municipal_candidate_grid,
            score_candidate_sites,
            MUNICIPAL_BOUNDS,
            DEFAULT_MIN_SPACING_KM,
            DEFAULT_POP_THRESHOLD,
            DEFAULT_CATCHMENT_RADIUS_M
        )

    reliable_all, approx_all = load_and_classify_stations(stations_file)
    scenario_gammas = {
        "Base": 0.00,
        "Low EV": 0.10,
        "Medium EV": 0.25,
        "High EV": 0.40
    }

    robust_results = {}

    for city in ["Surat", "Rajkot"]:
        st_rel = reliable_all[reliable_all["city"] == city].copy().reset_index(drop=True)
        st_app = approx_all[approx_all["city"] == city].copy().reset_index(drop=True)

        gdf_rel = gpd.GeoDataFrame(st_rel, geometry=[Point(lo, la) for lo, la in zip(st_rel["lon"], st_rel["lat"])], crs="EPSG:4326").to_crs("EPSG:32643")
        gdf_app = gpd.GeoDataFrame(st_app, geometry=[Point(lo, la) for lo, la in zip(st_app["lon"], st_app["lat"])], crs="EPSG:4326").to_crs("EPSG:32643")

        min_lon, min_lat, max_lon, max_lat = MUNICIPAL_BOUNDS[city]
        pad = 0.05
        with rasterio.open(raster_file) as src:
            win = from_bounds(min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad, src.transform)
            city_raster = src.read(1, window=win)
            win_trans = src.window_transform(win)
            city_raster = np.where(city_raster < 0, 0.0, city_raster)
            city_raster = np.nan_to_num(city_raster, nan=0.0)

        eligible, _ = build_municipal_candidate_grid(
            city,
            gdf_rel,
            gdf_app,
            city_raster,
            win_trans,
            min_spacing_km=DEFAULT_MIN_SPACING_KM[city],
            pop_threshold=DEFAULT_POP_THRESHOLD
        )

        all_ranked, top10_base = score_candidate_sites(
            eligible,
            gdf_rel,
            city_raster,
            win_trans,
            catchment_radius_m=DEFAULT_CATCHMENT_RADIUS_M
        )

        # Standardized population density
        dens = all_ranked["pop_density"].values
        mu_d, std_d = float(np.mean(dens)), float(np.std(dens)) if np.std(dens) > 0 else 1.0
        z_d = (dens - mu_d) / std_d

        scenario_top10 = {}
        scenario_sets = {}

        for sc_name, gamma in scenario_gammas.items():
            all_ranked[f"score_{sc_name}"] = all_ranked["score"] * (1.0 + gamma * z_d)
            top10_sc = all_ranked.sort_values(f"score_{sc_name}", ascending=False).head(10).copy().reset_index(drop=True)
            top10_sc["rank"] = range(1, len(top10_sc) + 1)
            scenario_top10[sc_name] = top10_sc
            scenario_sets[sc_name] = set(zip(top10_sc["lat"].round(4), top10_sc["lon"].round(4)))

        # Robust coordinate set (in top 10 under Low, Medium, AND High EV)
        robust_coords = (
            scenario_sets["Low EV"]
            .intersection(scenario_sets["Medium EV"])
            .intersection(scenario_sets["High EV"])
        )

        # Annotate Base top 10 candidates
        annotated_base = scenario_top10["Base"].copy()
        robust_status_list = []
        high_ev_ranks = []

        # Find High EV rank for each base site
        top10_high = scenario_top10["High EV"]
        high_coord_to_rank = {(round(r["lat"], 4), round(r["lon"], 4)): r["rank"] for _, r in top10_high.iterrows()}

        for _, r in annotated_base.iterrows():
            pt_key = (round(r["lat"], 4), round(r["lon"], 4))
            is_rob = pt_key in robust_coords
            status_str = "keeps top-10 rank under the assumed density rule" if is_rob else "drops out of top-10 under assumed density rule"
            robust_status_list.append(status_str)
            h_rk = high_coord_to_rank.get(pt_key, ">10")
            high_ev_ranks.append(h_rk)

        annotated_base["rank_base"] = annotated_base["rank"]
        annotated_base["rank_density_rule"] = high_ev_ranks
        annotated_base["robustness_status"] = robust_status_list

        robust_results[city] = {
            "all_ranked": all_ranked,
            "scenario_top10": scenario_top10,
            "robust_coords": robust_coords,
            "annotated_base": annotated_base
        }

    return robust_results


def main():
    parser = argparse.ArgumentParser(description="Audited EV Scenarios and Siting Robustness (PS000002 Module D Part 2).")
    parser.add_argument("--output-csv", default="data/processed/ev_scenarios.csv", help="Output path for EV scenarios CSV")
    parser.add_argument("--output-fig", default="outputs/figures/ev_scenarios.png", help="Output path for scenario figure")
    parser.add_argument("--stations-file", default="data/processed/stations_geocoded.csv", help="Clean stations path")
    parser.add_argument("--raster-file", default="data/raw/ind_ppp_2020_1km_UNadj.tif", help="WorldPop raster path")
    args = parser.parse_args()

    print("=" * 80)
    print("MODULE D: AUDITED EV SCENARIOS & SITING ROBUSTNESS (PART 2)")
    print("=" * 80)
    print("STRICT GUIDELINE VERIFICATION:")
    print("  - Target Source: NITI Aayog (2021) p. 12 (80% 3W, 40% bus, 70% commercial cab SALES-SHARE).")
    print("  - Stock Turnover: Converted sales targets to fleet share ceilings via vehicle turnover lags [ASSUMPTION].")
    print("  - Normalization: Multipliers normalized to identically 1.0000 in 2026 across all scenarios.")
    print("  - Baseline Volume: 3.760 mmscmd in 2026 (Q1 FY27 actual, quarterly_master.csv) [SOURCED].")
    print("  - Counterfactual ICE Growth: 4.0% p.a. CAGR without EV substitution [ASSUMPTION].")
    print("=" * 80)

    # 1. Generate normalized scenarios
    df_scenarios = build_normalized_ev_scenarios(years=range(2026, 2036))
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    df_scenarios.to_csv(args.output_csv, index=False)
    print(f"\n[Data] Normalized EV Scenario trajectories saved to {args.output_csv}")

    print("\nAudited & Normalized Projections (Selected Milestone Years):")
    cols_show = ["year", "scenario", "ev_fleet_share", "cng_demand_multiplier", "counterfactual_demand_mmscmd", "projected_cng_demand_mmscmd"]
    sub_show = df_scenarios[df_scenarios["year"].isin([2026, 2028, 2030, 2032, 2035])]
    print(sub_show[cols_show].to_string(index=False))

    # 2. Plot figure
    print("\nGenerating updated figure...")
    plot_ev_scenarios(df_scenarios, args.output_fig)

    # 3. Robustness evaluation
    print("\n" + "=" * 80)
    print("SITING ROBUSTNESS COMPARISON (WITH VS WITHOUT DENSITY BONUS)")
    print("=" * 80)
    print("Rule: Score_{density} = Score_{base} * [1 + gamma * Z_{density}] (gamma_High = 0.40)")
    print("Status: 'keeps top-10 rank under the assumed density rule' if in Top 10 across Low, Medium, and High.")
    print("=" * 80)

    robust_results = evaluate_siting_robustness(args.stations_file, args.raster_file)

    for city, res in robust_results.items():
        print(f"\n=== {city.upper()} CANDIDATE COMPARISON ===")
        print(f"Total candidate sites keeping Top 10 rank across all 3 EV scenarios: {len(res['robust_coords'])}")

        annotated = res["annotated_base"]
        cols_display = ["rank_base", "rank_density_rule", "lat", "lon", "unserved_pop", "pop_density", "robustness_status"]
        print(annotated[cols_display].to_string(index=False))


if __name__ == "__main__":
    main()
