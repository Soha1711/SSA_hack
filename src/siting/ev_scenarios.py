"""Module D (Part 2): EV Scenario Modeling and Siting Robustness (PS000002).

This script implements logistic S-curve adoption models across CNG-addressable vehicle
segments (three-wheelers, taxis/cars, buses) under Low, Medium, and High EV adoption.
It applies scenario multipliers to network-level demand forecasts (2026-2035),
re-ranks candidate siting locations under each scenario using an urban density resilience
rule, and identifies robust sites that remain in the Top 10 under all three scenarios.

STRICT CONSTRAINTS:
- No invented observed data.
- Every parameter is tagged as SOURCED (with citation and URL) or ASSUMPTION.
- Scores are relative priority scores, not sales forecasts.
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# SOURCED CITATIONS AND PARAMETER METADATA
# Source 1: NITI Aayog & Rocky Mountain Institute (RMI) 2021 report:
# "Mobilising Electric Vehicle Financing in India", URL: https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf
# - p. 12: Recommends 80% electrification for 2W/3W by 2030, 30-40% for cars (70% commercial cabs), and 40% for buses.
# Source 2: Gujarat Electric Vehicle Policy 2021 (Govt of Gujarat, Notification EVC-102021-125-P):
# URL: https://geda.gujarat.gov.in/policies_programs
# - Target of 200,000 EVs by 2025 across segments in Gujarat.

SCENARIO_METADATA = {
    "Low EV": {
        "description": "Slow transition constrained by charging infrastructure bottlenecks and battery replacement costs.",
        "3W": {"ceiling_L": 0.45, "source_L": "ASSUMPTION: Subdued adoption with partial commercial fleet turnover", "url_L": None,
               "steepness_k": 0.40, "source_k": "ASSUMPTION", "url_k": None,
               "midpoint_t0": 2030, "source_t0": "ASSUMPTION", "url_t0": None},
        "4W": {"ceiling_L": 0.20, "source_L": "ASSUMPTION: Slow passenger car EV penetration in non-metro Gujarat", "url_L": None,
               "steepness_k": 0.35, "source_k": "ASSUMPTION", "url_k": None,
               "midpoint_t0": 2032, "source_t0": "ASSUMPTION", "url_t0": None},
        "Bus": {"ceiling_L": 0.25, "source_L": "ASSUMPTION: Limited municipal e-bus procurement outside Ahmedabad", "url_L": None,
                "steepness_k": 0.35, "source_k": "ASSUMPTION", "url_k": None,
                "midpoint_t0": 2031, "source_t0": "ASSUMPTION", "url_t0": None},
    },
    "Medium EV": {
        "description": "Baseline policy transition aligned with NITI Aayog 2030 national targets and Gujarat EV Policy incentives.",
        "3W": {"ceiling_L": 0.65, "source_L": "SOURCED: NITI Aayog (2021) p. 12 (60-80% 3W electrification range)", "url_L": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
               "steepness_k": 0.45, "source_k": "ASSUMPTION: Standard S-curve logistic diffusion parameter", "url_k": None,
               "midpoint_t0": 2029, "source_t0": "ASSUMPTION: Fleet inflection year based on TCO parity", "url_t0": None},
        "4W": {"ceiling_L": 0.35, "source_L": "SOURCED: NITI Aayog (2021) p. 12 (30-40% 4W average target)", "url_L": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
               "steepness_k": 0.40, "source_k": "ASSUMPTION: Gradual commercial cab fleet adoption", "url_k": None,
               "midpoint_t0": 2030, "source_t0": "ASSUMPTION", "url_t0": None},
        "Bus": {"ceiling_L": 0.40, "source_L": "SOURCED: NITI Aayog (2021) p. 12 (40% Bus electrification target)", "url_L": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
                "steepness_k": 0.40, "source_k": "ASSUMPTION: State road transport corporation (GSRTC) phase-in", "url_k": None,
                "midpoint_t0": 2029, "source_t0": "ASSUMPTION", "url_t0": None},
    },
    "High EV": {
        "description": "Aggressive disruption with rapid TCO parity, PM-eBus Sewa expansion, and urban ICE restrictions.",
        "3W": {"ceiling_L": 0.80, "source_L": "SOURCED: NITI Aayog (2021) p. 12 (80% 2W/3W target ceiling)", "url_L": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
               "steepness_k": 0.55, "source_k": "ASSUMPTION: Accelerated transition driven by battery swapping", "url_k": None,
               "midpoint_t0": 2028, "source_t0": "ASSUMPTION: Rapid municipal commercial conversion", "url_t0": None},
        "4W": {"ceiling_L": 0.50, "source_L": "ASSUMPTION: 70% cab fleet + 30% private cars yielding 50% composite ceiling", "url_L": "https://www.niti.gov.in/sites/default/files/2021-04/Mobilising-Electric-Vehicle-Financing-in-India.pdf",
               "steepness_k": 0.45, "source_k": "ASSUMPTION", "url_k": None,
               "midpoint_t0": 2029, "source_t0": "ASSUMPTION", "url_t0": None},
        "Bus": {"ceiling_L": 0.60, "source_L": "ASSUMPTION: 100% municipal city bus + 40% intercity bus electrification", "url_L": None,
                "steepness_k": 0.50, "source_k": "ASSUMPTION", "url_k": None,
                "midpoint_t0": 2028, "source_t0": "ASSUMPTION", "url_t0": None},
    }
}

# SEGMENT WEIGHTS IN CNG DEMAND (ASSUMPTION based on Gujarat CGD fleet profile)
# 3W: Auto-rickshaws and light passenger commercial vehicles
# 4W: App-based commercial taxis, shared fleet, and private cars
# Bus: Municipal transit (BRTS/AMTS) and private intercity passenger buses
SEGMENT_WEIGHTS = {
    "3W": 0.50,   # ASSUMPTION: 50% of Gujarat retail CNG volume
    "4W": 0.35,   # ASSUMPTION: 35% of Gujarat retail CNG volume
    "Bus": 0.15   # ASSUMPTION: 15% of Gujarat retail CNG volume
}

# Network Baseline Volume and Organic Growth
# Q1 FY27 actual annualized volume is 3.76 mmscmd (from quarterly_master.csv)
BASE_YEAR = 2026
BASE_VOLUME_MMSCMD = 3.76  # Sourced from data/processed/quarterly_master.csv (Q1 FY27 actual: 3.76 mmscmd)
COUNTERFACTUAL_CAGR = 0.04  # ASSUMPTION: 4.0% p.a. organic ICE volume growth without EV substitution


def logistic_s_curve(t, L, k, t0):
    """Logistic S-curve formula: S(t) = L / (1 + exp(-k * (t - t0)))."""
    return L / (1.0 + np.exp(-k * (t - t0)))


def build_ev_scenarios(years=range(2026, 2036)):
    """Generate annual EV adoption shares and CNG demand multipliers for all scenarios."""
    rows = []
    for sc_name, params in SCENARIO_METADATA.items():
        for yr in years:
            s_3w = float(logistic_s_curve(yr, params["3W"]["ceiling_L"], params["3W"]["steepness_k"], params["3W"]["midpoint_t0"]))
            s_4w = float(logistic_s_curve(yr, params["4W"]["ceiling_L"], params["4W"]["steepness_k"], params["4W"]["midpoint_t0"]))
            s_bus = float(logistic_s_curve(yr, params["Bus"]["ceiling_L"], params["Bus"]["steepness_k"], params["Bus"]["midpoint_t0"]))

            # Weighted composite EV fleet share
            ev_share = (
                SEGMENT_WEIGHTS["3W"] * s_3w
                + SEGMENT_WEIGHTS["4W"] * s_4w
                + SEGMENT_WEIGHTS["Bus"] * s_bus
            )

            # CNG demand multiplier (1 - EV displacement share)
            multiplier = 1.0 - ev_share

            # Counterfactual ICE demand without EV (4% CAGR from 2026 base 3.76 mmscmd)
            cf_demand = BASE_VOLUME_MMSCMD * ((1.0 + COUNTERFACTUAL_CAGR) ** (yr - BASE_YEAR))

            # Projected network CNG demand
            proj_demand = cf_demand * multiplier

            rows.append({
                "year": yr,
                "scenario": sc_name,
                "ev_share_3w": round(s_3w, 4),
                "ev_share_4w": round(s_4w, 4),
                "ev_share_bus": round(s_bus, 4),
                "ev_share": round(ev_share, 4),
                "cng_demand_multiplier": round(multiplier, 4),
                "counterfactual_demand_mmscmd": round(cf_demand, 3),
                "projected_cng_demand_mmscmd": round(proj_demand, 3)
            })

    return pd.DataFrame(rows)


def plot_ev_scenarios(df_scenarios, output_png_path="outputs/figures/ev_scenarios.png"):
    """Plot 3-panel figure: Segment EV adoption curves, CNG Multipliers, and Network Demand."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), dpi=300)

    colors = {
        "Low EV": "#2ca02c",      # Green (favorable for CNG)
        "Medium EV": "#ff7f0e",   # Orange (baseline)
        "High EV": "#d62728"      # Red (disruptive)
    }

    # -------------------------------------------------------------
    # Panel 1: S-Curve EV Adoption by Scenario and Segment
    # -------------------------------------------------------------
    ax1 = axes[0]
    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax1.plot(sub["year"], sub["ev_share"] * 100, label=f"{sc_name} (Composite)", color=colors[sc_name], linewidth=2.5)
        ax1.plot(sub["year"], sub["ev_share_3w"] * 100, color=colors[sc_name], linestyle=":", alpha=0.7, label=f"{sc_name} (3W)" if sc_name == "Medium EV" else "")
        ax1.plot(sub["year"], sub["ev_share_4w"] * 100, color=colors[sc_name], linestyle="--", alpha=0.7, label=f"{sc_name} (4W)" if sc_name == "Medium EV" else "")
        ax1.plot(sub["year"], sub["ev_share_bus"] * 100, color=colors[sc_name], linestyle="-.", alpha=0.7, label=f"{sc_name} (Bus)" if sc_name == "Medium EV" else "")

    ax1.set_title("A. EV Adoption S-Curves by Segment\n(3W: 50%, 4W: 35%, Bus: 15% [ASSUMPTION])", fontsize=11, fontweight="bold")
    ax1.set_xlabel("Year", fontsize=10)
    ax1.set_ylabel("EV Fleet Share (%)", fontsize=10)
    ax1.set_ylim(0, 85)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=8, framealpha=0.9)

    # -------------------------------------------------------------
    # Panel 2: CNG Demand Multiplier
    # -------------------------------------------------------------
    ax2 = axes[1]
    ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1.5, label="Baseline ICE Index (1.00)")
    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax2.plot(sub["year"], sub["cng_demand_multiplier"], marker="o", markersize=4, label=f"{sc_name} Multiplier", color=colors[sc_name], linewidth=2.2)

    ax2.set_title("B. CNG Demand Multiplier Trajectory\n(Multiplier = 1.0 - EV Fleet Share)", fontsize=11, fontweight="bold")
    ax2.set_xlabel("Year", fontsize=10)
    ax2.set_ylabel("CNG Demand Multiplier", fontsize=10)
    ax2.set_ylim(0.40, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.9)

    # -------------------------------------------------------------
    # Panel 3: GGCL Network CNG Demand Projections
    # -------------------------------------------------------------
    ax3 = axes[2]
    # Counterfactual ICE
    sub_med = df_scenarios[df_scenarios["scenario"] == "Medium EV"]
    ax3.plot(sub_med["year"], sub_med["counterfactual_demand_mmscmd"], color="black", linestyle="--", linewidth=2.0, label="Counterfactual ICE (4% CAGR)")

    for sc_name in ["Low EV", "Medium EV", "High EV"]:
        sub = df_scenarios[df_scenarios["scenario"] == sc_name]
        ax3.plot(sub["year"], sub["projected_cng_demand_mmscmd"], marker="s", markersize=4, label=f"Projected: {sc_name}", color=colors[sc_name], linewidth=2.2)

    # Fill gap between Counterfactual and High EV
    sub_high = df_scenarios[df_scenarios["scenario"] == "High EV"]
    ax3.fill_between(
        sub_med["year"],
        sub_high["projected_cng_demand_mmscmd"],
        sub_med["counterfactual_demand_mmscmd"],
        color="red",
        alpha=0.10,
        label="EV Demand Destruction Gap"
    )

    ax3.set_title("C. Network CNG Demand Trajectory\n(Base: 3.76 mmscmd Q1 FY27 Actual [SOURCED])", fontsize=11, fontweight="bold")
    ax3.set_xlabel("Year", fontsize=10)
    ax3.set_ylabel("Network CNG Sales (mmscmd)", fontsize=10)
    ax3.set_ylim(2.0, 6.0)
    ax3.grid(True, linestyle=":", alpha=0.6)
    ax3.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    plt.savefig(output_png_path, dpi=300)
    plt.close()
    print(f"  [Figure] Saved EV scenario trajectory figure to {output_png_path}")


def evaluate_siting_robustness(
    stations_file="data/processed/stations_geocoded.csv",
    raster_file="data/raw/ind_ppp_2020_1km_UNadj.tif",
    min_cand_spacing_km=0.0
):
    """Re-rank candidate sites under Low, Medium, and High EV adoption and find robust sites.

    RULE DEFINITION (Urban Density Fleet Resilience Rule [ASSUMPTION]):
    As statewide EV adoption increases and overall CNG demand contracts, peripheral and
    suburban CNG stations experience severe demand erosion as personal vehicles electrify.
    In contrast, dense urban corridors retain concentrated commercial fleet activity
    (auto-rickshaws, shared taxis, intra-city buses) due to continuous turnaround needs,
    depot proximity, and lack of residential charging space.
    Therefore, candidate scores under scenario s are modified as:
        Score_{i, s} = Score_{i, base} * [1.0 + gamma_s * Z_{density, i}]
    where:
        - Z_{density, i} = (PopDensity_i - mean_density) / std_density
        - gamma_base = 0.00 (Pure spatial coverage)
        - gamma_Low = 0.10  (Mild fleet density preference)
        - gamma_Medium = 0.25 (Moderate fleet consolidation)
        - gamma_High = 0.40 (Strong flight to commercial fleet density)

    ROBUST SITES DEFINITION:
    Candidate sites that remain in the Top 10 ranking under ALL THREE EV scenarios (Low, Medium, and High).
    """
    try:
        from src.siting.rank_sites import (
            load_clean_stations,
            extract_city_raster,
            build_candidate_grid,
            score_candidate_sites,
            CITY_CENTRES,
            DEFAULT_MIN_SPACING_KM,
            DEFAULT_POP_THRESHOLD
        )
    except ImportError:
        from rank_sites import (
            load_clean_stations,
            extract_city_raster,
            build_candidate_grid,
            score_candidate_sites,
            CITY_CENTRES,
            DEFAULT_MIN_SPACING_KM,
            DEFAULT_POP_THRESHOLD
        )

    clean_stations = load_clean_stations(stations_file)
    scenario_gammas = {
        "Base": 0.00,
        "Low EV": 0.10,
        "Medium EV": 0.25,
        "High EV": 0.40
    }

    robust_results = {}

    for city in ["Surat", "Rajkot"]:
        st_city = clean_stations[clean_stations["city"] == city].copy().reset_index(drop=True)
        gdf_st = gpd.GeoDataFrame(
            st_city,
            geometry=[Point(lo, la) for lo, la in zip(st_city["lon"], st_city["lat"])],
            crs="EPSG:4326"
        ).to_crs("EPSG:32643")

        city_raster, win_trans = extract_city_raster(gdf_st, raster_file)
        clat, clon = CITY_CENTRES[city]

        # Generate candidate grid and base scoring
        urban_cand, _ = build_candidate_grid(clat, clon, city_raster, win_trans, pop_threshold=DEFAULT_POP_THRESHOLD)
        all_ranked, top10_base = score_candidate_sites(
            urban_cand,
            gdf_st,
            city_raster,
            win_trans,
            min_spacing_km=DEFAULT_MIN_SPACING_KM[city],
            min_cand_spacing_km=min_cand_spacing_km
        )

        # Compute standardized local population density
        dens = all_ranked["pop_density"].values
        mu_d, std_d = float(np.mean(dens)), float(np.std(dens)) if np.std(dens) > 0 else 1.0
        z_d = (dens - mu_d) / std_d

        scenario_top10 = {}
        scenario_sets = {}

        for sc_name, gamma in scenario_gammas.items():
            all_ranked[f"score_{sc_name}"] = all_ranked["score"] * (1.0 + gamma * z_d)
            top10_sc = all_ranked.sort_values(f"score_{sc_name}", ascending=False).head(10).copy().reset_index(drop=True)
            top10_sc["rank"] = range(1, 11)
            scenario_top10[sc_name] = top10_sc
            scenario_sets[sc_name] = set(zip(top10_sc["lat"].round(4), top10_sc["lon"].round(4)))

        # Find robust coordinates (in top 10 under Low, Medium, AND High)
        robust_coords = (
            scenario_sets["Low EV"]
            .intersection(scenario_sets["Medium EV"])
            .intersection(scenario_sets["High EV"])
        )

        # Flag robust candidates in Base top 10
        top10_base_annotated = scenario_top10["Base"].copy()
        is_robust_list = []
        for _, r in top10_base_annotated.iterrows():
            pt_key = (round(r["lat"], 4), round(r["lon"], 4))
            is_robust_list.append(pt_key in robust_coords)
        top10_base_annotated["is_robust"] = is_robust_list

        robust_results[city] = {
            "all_ranked": all_ranked,
            "scenario_top10": scenario_top10,
            "robust_coords": robust_coords,
            "top10_base_annotated": top10_base_annotated
        }

    return robust_results


def main():
    parser = argparse.ArgumentParser(description="EV Scenarios and Site Robustness (PS000002 Module D Part 2).")
    parser.add_argument("--output-csv", default="data/processed/ev_scenarios.csv", help="Output path for EV scenarios CSV")
    parser.add_argument("--output-fig", default="outputs/figures/ev_scenarios.png", help="Output path for scenario figure")
    parser.add_argument("--stations-file", default="data/processed/stations_geocoded.csv", help="Clean stations path")
    parser.add_argument("--raster-file", default="data/raw/ind_ppp_2020_1km_UNadj.tif", help="WorldPop raster path")
    args = parser.parse_args()

    print("=" * 80)
    print("MODULE D: EV SCENARIOS & SITING ROBUSTNESS (PART 2)")
    print("=" * 80)
    print("STRICT GUIDELINE VERIFICATION:")
    print("  - Models: Logistic S-curves applied across 3W, 4W, and Bus segments.")
    print("  - Parameters: SOURCED (NITI Aayog 2021 targets) vs ASSUMPTION explicitly tagged.")
    print("  - Baseline Volume: 3.76 mmscmd (Q1 FY27 actual, quarterly_master.csv) [SOURCED].")
    print("  - Counterfactual ICE Growth: 4.0% p.a. CAGR without EV substitution [ASSUMPTION].")
    print("  - Multipliers: M(t) = 1.0 - EV_share(t).")
    print("=" * 80)

    # 1. Generate EV scenarios dataframe
    df_scenarios = build_ev_scenarios(years=range(2026, 2036))

    # Save to CSV
    os.makedirs(os.path.dirname(args.output_csv), exist_ok=True)
    df_scenarios.to_csv(args.output_csv, index=False)
    print(f"\n[Data] EV Scenario trajectories saved to {args.output_csv}")

    # Display key milestones
    print("\nScenario Projections Summary (Selected Milestone Years):")
    cols_show = ["year", "scenario", "ev_share", "cng_demand_multiplier", "counterfactual_demand_mmscmd", "projected_cng_demand_mmscmd"]
    sub_show = df_scenarios[df_scenarios["year"].isin([2026, 2028, 2030, 2032, 2035])]
    print(sub_show[cols_show].to_string(index=False))

    # 2. Plot scenario trajectories
    print("\nGenerating publication-quality figure...")
    plot_ev_scenarios(df_scenarios, args.output_fig)

    # 3. Re-rank Part 1 candidate sites under EV scenarios
    print("\n" + "=" * 80)
    print("PART 1 SITES RE-RANKING & ROBUST SITES EVALUATION")
    print("=" * 80)
    print("Urban Density Fleet Resilience Rule [ASSUMPTION]:")
    print("  Score_{i, s} = Score_{i, base} * [1 + gamma_s * Z_{density, i}]")
    print("  where gamma_Low=0.10, gamma_Medium=0.25, gamma_High=0.40.")
    print("  Robust Sites: Candidates remaining in Top 10 under Low, Medium, AND High EV.")
    print("=" * 80)

    robust_results = evaluate_siting_robustness(
        stations_file=args.stations_file,
        raster_file=args.raster_file
    )

    for city, res in robust_results.items():
        print(f"\n=== {city.upper()} CANDIDATE RE-RANKING & ROBUST SITES ===")
        print(f"Total candidate sites remaining in Top 10 across all 3 EV scenarios: {len(res['robust_coords'])}")
        
        annotated = res["top10_base_annotated"]
        cols_base = ["rank", "lat", "lon", "unserved_pop", "pop_density", "score", "is_robust"]
        print("\nPart 1 Base Top 10 Sites with EV Robustness Status:")
        print(annotated[cols_base].to_string(index=False))

        # Show Top 5 under High EV
        top5_high = res["scenario_top10"]["High EV"].head(5)
        print(f"\nTop 5 Candidates under High EV Scenario (Aggressive Density Flight):")
        print(top5_high[["rank", "lat", "lon", "unserved_pop", "pop_density", "score_High EV"]].to_string(index=False))


if __name__ == "__main__":
    main()
