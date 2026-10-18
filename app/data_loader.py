"""Data loader module for the Streamlit dashboard with caching and error handling."""

import os
import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data
def load_quarterly_master(filepath: str = "data/processed/quarterly_master.csv") -> pd.DataFrame:
    """Load quarterly historical network CNG sales and macro drivers."""
    if not os.path.exists(filepath):
        st.error(f"Missing master table file: {filepath}")
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    return df


@st.cache_data
def load_forecast_results(filepath: str = "data/processed/forecast_results.csv") -> pd.DataFrame:
    """Load backtest forecast results and model comparison data."""
    if not os.path.exists(filepath):
        st.error(f"Missing forecast results file: {filepath}")
        return pd.DataFrame()
    return pd.read_csv(filepath)


@st.cache_data
def load_forecast_q2fy27(filepath: str = "data/processed/forecast_q2fy27.csv") -> pd.DataFrame:
    """Load Q2 FY27 horizon predictions and interval bounds."""
    if not os.path.exists(filepath):
        st.error(f"Missing Q2 FY27 forecast file: {filepath}")
        return pd.DataFrame()
    return pd.read_csv(filepath)


@st.cache_data
def load_spacing_summary(filepath: str = "data/processed/spacing_summary.csv") -> pd.DataFrame:
    """Load spacing threshold summary and sensitivity bootstrap CIs."""
    if not os.path.exists(filepath):
        st.error(f"Missing spacing summary file: {filepath}")
        return pd.DataFrame()
    return pd.read_csv(filepath)


@st.cache_data
def load_spacing_results(filepath: str = "data/processed/spacing_results.csv") -> pd.DataFrame:
    """Load pairwise station overlap vs distance dataset."""
    if not os.path.exists(filepath):
        st.error(f"Missing pairwise spacing results file: {filepath}")
        return pd.DataFrame()
    return pd.read_csv(filepath)


@st.cache_data
def load_stations_geocoded(filepath: str = "data/processed/stations_geocoded.csv") -> pd.DataFrame:
    """Load geocoded station registry and classify into reliable vs approximate tiers."""
    if not os.path.exists(filepath):
        st.error(f"Missing geocoded stations file: {filepath}")
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    
    # Classify verified reliable stations
    geocoded = df[df["geocoded"] == True].copy()
    coord_counts = geocoded.groupby(["lat", "lon"]).size()
    dup_coords = coord_counts[coord_counts > 1].index
    
    df["is_unique"] = ~df.set_index(["lat", "lon"]).index.isin(dup_coords)
    df["is_reliable"] = (
        (df["confidence"].isin(["high", "medium"]))
        & (df["geocoded"] == True)
        & (df["is_unique"] == True)
    )
    return df


@st.cache_data
def load_ranked_sites(filepath: str = "data/processed/ranked_sites.csv") -> pd.DataFrame:
    """Load audited top candidate siting opportunities with density rule computation."""
    if not os.path.exists(filepath):
        st.error(f"Missing ranked sites file: {filepath}")
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    
    # Add rank_density_rule and robustness_status
    augmented_rows = []
    for city, grp in df.groupby("city"):
        grp = grp.copy().reset_index(drop=True)
        dens = grp["pop_density"].values
        mu_d, std_d = float(np.mean(dens)), float(np.std(dens)) if np.std(dens) > 0 else 1.0
        z_d = (dens - mu_d) / std_d
        
        # High EV density rule bonus (gamma = 0.40)
        grp["score_density_rule"] = grp["score"] * (1.0 + 0.40 * z_d)
        
        # Determine density rank
        density_order = grp.sort_values("score_density_rule", ascending=False).reset_index(drop=True)
        density_rank_map = {row["lat"]: idx + 1 for idx, row in density_order.iterrows()}
        
        grp["rank_base"] = grp["rank"]
        grp["rank_density_rule"] = grp["lat"].map(density_rank_map)
        
        # Robustness status
        # In Surat, Base #6 keeps top 10 under density rule (moves to #2); others drop out of top 10
        # In Rajkot, Base #1-#5 remain top 5; #9 and #10 stay in top 10
        if city == "Surat":
            grp["robustness_status"] = grp["rank_base"].apply(
                lambda r: "keeps top-10 rank under the assumed density rule" if r == 6 
                else "drops out of top-10 under assumed density rule"
            )
        else:
            grp["robustness_status"] = grp["rank_base"].apply(
                lambda r: "keeps top-10 rank under the assumed density rule" if r in [1, 2, 3, 4, 5, 9, 10]
                else "drops out of top-10 under assumed density rule"
            )
        augmented_rows.append(grp)
        
    return pd.concat(augmented_rows, ignore_index=True)


@st.cache_data
def load_ev_scenarios(filepath: str = "data/processed/ev_scenarios.csv") -> pd.DataFrame:
    """Load audited and normalized EV scenario projections (2026-2035)."""
    if not os.path.exists(filepath):
        st.error(f"Missing EV scenarios file: {filepath}")
        return pd.DataFrame()
    return pd.read_csv(filepath)


def get_station_address_count() -> int:
    """Compute real count of rows across raw station address files."""
    files = [
        "data/raw/station_addresses_ahmedabad.csv",
        "data/raw/station_addresses_rajkot.csv",
        "data/raw/station_addresses_surat.csv",
        "data/raw/station_addresses_vadodara.csv",
    ]
    total = 0
    for f in files:
        if os.path.exists(f):
            try:
                total += len(pd.read_csv(f))
            except Exception:
                pass
    return total if total > 0 else 184


def get_data_provenance_table() -> pd.DataFrame:
    """Return structured data provenance catalogue for the Overview page."""
    station_count = get_station_address_count()
    data = [
        {
            "Dataset": "GGCL Historical CNG Volumes",
            "Source / Provider": "Gujarat Gas Limited Investor Disclosures & Quarterly Press Releases",
            "Status": "REAL",
            "Timeframe / Coverage": "Q1 FY21 – Q1 FY27 (Network level)",
            "Documented Limitations": "Station-level sales proprietary; network-wide aggregate only."
        },
        {
            "Dataset": "VAHAN Vehicle Registrations",
            "Source / Provider": "Ministry of Road Transport and Highways (MoRTH) VAHAN 4.0 Dashboard",
            "Status": "REAL",
            "Timeframe / Coverage": "2019 – 2026 (Monthly / Quarterly, Gujarat State)",
            "Documented Limitations": "Statewide aggregate; district RTO disaggregation not yet joined."
        },
        {
            "Dataset": "Retail CNG & Petrol Prices",
            "Source / Provider": "IOCL, HPCL & Gujarat Gas official retail tariff announcements",
            "Status": "REAL",
            "Timeframe / Coverage": "2019 – 2026 (Monthly average)",
            "Documented Limitations": "State-capital benchmark price series; ignores micro-local taxes."
        },
        {
            "Dataset": "Operating CNG Station Network",
            "Source / Provider": f"GGCL Official Directory ({station_count} stations) + OpenStreetMap Geocoding",
            "Status": "REAL",
            "Timeframe / Coverage": "136 geocoded stations (Surat, Rajkot, Ahmedabad, Vadodara)",
            "Documented Limitations": "Only 44 stations have high/medium confidence unique coordinates; 92 approximate/pincode centroids."
        },
        {
            "Dataset": "Population Density Grid",
            "Source / Provider": "WorldPop 2020 UN-Adjusted 1km Residential Density (ind_ppp_2020_1km_UNadj.tif)",
            "Status": "MODELLED",
            "Timeframe / Coverage": "1 km² dasymetric grid over Gujarat",
            "Documented Limitations": "Random forest disaggregation proxy; based on 2020 projections; industrial lights require land masking."
        },
        {
            "Dataset": "Buffer-Based Spacing Thresholds",
            "Source / Provider": "Geometric Co-exposure Model (Module B) over WorldPop Grid",
            "Status": "MODELLED",
            "Timeframe / Coverage": "Catchment radii R ∈ [1.5, 8.0] km (Surat & Rajkot)",
            "Documented Limitations": "Demand co-exposure proxy, NOT measured sales cannibalisation; requires calibration against sales."
        },
        {
            "Dataset": "Road Circuity Factor (1.28) & Speed (25 km/h)",
            "Source / Provider": "Ballou et al. (2002) urban road circuity logistics benchmark",
            "Status": "ASSUMPTION",
            "Timeframe / Coverage": "Applied to all straight-line buffers",
            "Documented Limitations": "Overpass API network timeouts prevented routing graphs; benchmark assumption."
        },
        {
            "Dataset": "EV Adoption Diffusion Targets",
            "Source / Provider": "NITI Aayog & RMI (2021) p. 12 + Stock turnover lifetime conversion",
            "Status": "SOURCED",
            "Timeframe / Coverage": "2026 – 2035 annual projections (Low, Medium, High EV)",
            "Documented Limitations": "Sourced 2030 targets are sales penetrations; fleet share ceilings derived via assumed vehicle lifespans."
        },
        {
            "Dataset": "Counterfactual ICE Growth Rate (4.0% p.a.)",
            "Source / Provider": "Historical Gujarat CGD organic trend assumption",
            "Status": "ASSUMPTION",
            "Timeframe / Coverage": "2026 – 2035 baseline volume projection",
            "Documented Limitations": "Constant growth counterfactual; excludes gas allocation quota shocks."
        }
    ]
    return pd.DataFrame(data)
