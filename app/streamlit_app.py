"""CNG Demand Planner - Main Streamlit Application (PS000002).

Seva First Innovation Challenge 2026
Team ID: TM000846
Problem: Station-Level Demand Forecasting for CNG Sales to Optimize Network Expansion (Gujarat Gas Limited)
"""

import sys
import os
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# Add root directory to sys.path to allow imports from app/
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("app"))

from app.components import (
    badge_html,
    render_page_badges,
    render_notice_banner,
    render_footer
)
from app.data_loader import (
    load_quarterly_master,
    load_forecast_results,
    load_forecast_q2fy27,
    load_spacing_summary,
    load_spacing_results,
    load_stations_geocoded,
    load_ranked_sites,
    load_ev_scenarios,
    get_data_provenance_table
)

# Page Configuration
st.set_page_config(
    page_title="CNG Demand Planner | GGCL Network Expansion",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished aesthetic and tag rendering
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }
    h1, h2, h3 {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #0f172a;
    }
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #0066cc;
    }
    .metric-label {
        font-size: 13px;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Gujarat_Gas_logo.png/320px-Gujarat_Gas_logo.png", width=180) if False else None
st.sidebar.markdown("## ⛽ CNG Demand Planner")
st.sidebar.caption("Gujarat Gas Limited | Network Expansion Optimization")
st.sidebar.markdown("**Challenge:** PS000002 | **Team:** TM000846")
st.sidebar.markdown("---")

PAGES = [
    "1. Overview",
    "2. Demand forecast",
    "3. Station spacing",
    "4. Coverage gaps (illustrative)",
    "5. EV scenarios",
    "6. Limitations and next steps"
]

page_selection = st.sidebar.radio("Navigate", PAGES, index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Status Legend")
st.sidebar.markdown(f"{badge_html('REAL')} Observed empirical records", unsafe_allow_html=True)
st.sidebar.markdown(f"{badge_html('MODELLED')} Statistical / geospatial model", unsafe_allow_html=True)
st.sidebar.markdown(f"{badge_html('ASSUMPTION')} Engineering / policy assumption", unsafe_allow_html=True)
st.sidebar.markdown(f"{badge_html('SOURCED')} Published external benchmark", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.caption("Built for Seva First Innovation Challenge 2026. Self-contained execution without external API dependencies.")


# ==============================================================================
# PAGE 1: OVERVIEW
# ==============================================================================
if page_selection == "1. Overview":
    st.title("Network Expansion Decision Support System")
    st.subheader("PS000002: Station-Level Demand Forecasting for CNG Sales to Optimize Network Expansion")
    render_page_badges(["REAL", "MODELLED", "ASSUMPTION", "SOURCED"])

    render_notice_banner(
        "Station-level sales are proprietary to Gujarat Gas Company Limited (GGCL). Network-level and geographic analyses use publicly available, verified datasets. The pipeline is designed to accept proprietary station telemetry.",
        banner_type="warning"
    )

    # Core Problem & Solution Overview
    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("""
        ### The Commercial Problem
        City Gas Distribution (CGD) companies like **Gujarat Gas Limited (GGCL)** face capital allocation trade-offs when expanding their retail Compressed Natural Gas (CNG) network:
        - **Cannibalisation vs. Access**: Adding stations too close together splits existing vehicle throughput rather than capturing new demand.
        - **Electrification Headwinds**: Commercial fleets (3-wheelers, app-based taxis, city buses) are undergoing accelerated electrification under state and national policy mandates.
        - **Data Asymmetry**: While aggregate quarterly sales are reported in earnings disclosures, station-level hourly dispensing volumes and queue lengths are closely guarded commercial assets.
        """)

    with col2:
        st.markdown("""
        ### Solution Architecture
        This platform delivers an end-to-end analytical framework organized into **four engines**:
        1. **Demand Forecast**: Time-series model (1.76% MAPE) linking fuel price ratios and fleet diffusion to forecast quarterly demand.
        2. **Station Spacing**: Spatial buffer co-exposure model on WorldPop population density establishing minimum station separation.
        3. **Coverage Gaps**: Land-masked municipal candidate grid prioritizing unserved demand gaps under operating station exclusion zones.
        4. **EV Scenarios**: Stock turnover S-curve model projecting 2026–2035 CNG volume contraction across vehicle categories.
        """)

    st.markdown("---")

    # High-level Key Metrics
    st.markdown("### Executive Highlights")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Winning Model Out-of-Sample Error</div>
            <div class="metric-value">1.76%</div>
            <div style="font-size: 12px; color: #10b981; font-weight: 600;">MAPE vs. 3.35% Baseline Naive</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Q2 FY27 Point Forecast</div>
            <div class="metric-value">3.88 mmscmd</div>
            <div style="font-size: 12px; color: #3b82f6; font-weight: 600;">80% CI: [3.80, 3.97] mmscmd</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">Surat Urban Spacing (20% Overlap)</div>
            <div class="metric-value">3.11 km</div>
            <div style="font-size: 12px; color: #64748b; font-weight: 600;">3.98 km Road Equivalent (1.28 Circuity)</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-label">2030 Baseline Demand Impact</div>
            <div class="metric-value">-16.9%</div>
            <div style="font-size: 12px; color: #f59e0b; font-weight: 600;">Medium EV vs. 4% CAGR Counterfactual</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Data Provenance Table
    st.markdown("### Data Provenance & Lineage Catalogue")
    st.markdown("Every dataset utilized across the repository is audited and categorized below:")
    
    prov_df = get_data_provenance_table()
    
    # Format table with HTML badges
    prov_display = prov_df.copy()
    prov_display["Status"] = prov_display["Status"].apply(badge_html)
    st.write(
        prov_display.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )
    st.caption("All datasets are locally versioned in `data/raw` and `data/processed`. No live external API calls are made during app execution.")

    render_footer()


# ==============================================================================
# PAGE 2: NETWORK DEMAND FORECAST
# ==============================================================================
elif page_selection == "2. Demand forecast":
    st.title("Network-level CNG demand forecast")
    st.subheader("Historical Backtest, Model Comparison, and Q2 FY27 Projection")
    render_page_badges(["REAL", "MODELLED"])

    df_master = load_quarterly_master()
    df_results = load_forecast_results()
    df_q2 = load_forecast_q2fy27()

    if df_master.empty or df_results.empty or df_q2.empty:
        st.error("Forecast data files could not be loaded from data/processed/.")
    else:
        # Forecast Callout Card
        ridge_q2 = df_q2[df_q2["model"].str.contains("Ridge", case=False, na=False)].iloc[0]
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"""
            <div style="background-color: #f0f7ff; border: 1.5px solid #0066cc; border-radius: 8px; padding: 18px 22px; margin-bottom: 20px;">
                <div style="font-size: 13px; font-weight: 700; color: #0066cc; text-transform: uppercase; letter-spacing: 0.5px;">
                    {badge_html('MODELLED')} Official Horizon Forecast | Q2 FY27
                </div>
                <div style="display: flex; align-items: baseline; gap: 15px; margin-top: 6px;">
                    <div style="font-size: 38px; font-weight: 800; color: #0f172a;">{ridge_q2['point_forecast_mmscmd']:.3f} mmscmd</div>
                    <div style="font-size: 15px; color: #475569; font-weight: 600;">80% Empirical CI: [{ridge_q2['lower_80_mmscmd']:.3f}, {ridge_q2['upper_80_mmscmd']:.3f}] mmscmd</div>
                </div>
                <div style="font-size: 13px; color: #64748b; margin-top: 6px; line-height: 1.4;">
                    Winning Specification: Standardized Ridge Regression (Lag-1 volume + cumulative VAHAN fleet proxy).
                    <br><strong>Note:</strong> The actual Q2 FY27 volume will be officially published by Gujarat Gas Limited during the Q2 FY27 investor release on <strong>5 November 2026</strong>.
                </div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px 20px; height: 100%;">
                <div style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase;">Benchmark Performance</div>
                <div style="font-size: 22px; font-weight: 700; color: #10b981; margin-top: 4px;">1.76% MAPE</div>
                <div style="font-size: 13px; color: #475569;">RMSE: 0.079 mmscmd | MAE: 0.055 mmscmd</div>
                <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
                    Evaluated via rolling walk-forward cross-validation across 10 quarters (Q4 FY24 – Q1 FY27).
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Calculate performance metrics dynamically from forecast_results.csv
        metrics = []
        models_meta = [
            ("naive", "Naive Lag-1 Baseline", "Flat extrapolation of previous quarter volume"),
            ("seasonal_naive", "Seasonal Naive (Lag-4)", "Same quarter previous fiscal year volume"),
            ("linear_regression", "Linear OLS (Lag-1 + Fleet)", "2-feature unregularized linear regression"),
            ("linear_3feat", "Linear OLS (Lag-1 + Fleet + Price)", "3-feature unregularized specification with petrol price gap"),
            ("ridge_regression", "Standardized Ridge (Winning Model)", "L2-regularized standardized formulation (alpha=1.0)")
        ]
        
        for col_name, display_name, desc in models_meta:
            if col_name in df_results.columns:
                actual = df_results["actual"]
                pred = df_results[col_name]
                mape = np.mean(np.abs((actual - pred) / actual)) * 100.0
                rmse = np.sqrt(np.mean((actual - pred) ** 2))
                mae = np.mean(np.abs(actual - pred))
                is_winner = col_name == "ridge_regression"
                metrics.append({
                    "Model": display_name + (" ⭐ (SELECTED)" if is_winner else ""),
                    "Specification & Drivers": desc,
                    "MAPE (%)": f"{mape:.2f}%",
                    "RMSE (mmscmd)": f"{rmse:.3f}",
                    "MAE (mmscmd)": f"{mae:.3f}",
                    "Selected Status": "WINNER" if is_winner else "BENCHMARK"
                })
                
        metrics_df = pd.DataFrame(metrics)
        n_models = len(metrics_df)

        # Plotly Historical & Backtest Chart
        st.markdown("### Historical Sales vs. Model Backtest Predictions")
        st.caption(f"Best of {n_models} models tested over 10 quarters (Q4 FY24 – Q1 FY27 rolling walk-forward backtest). All models tested are shown.")

        fig = go.Figure()

        # Full historical real series
        fig.add_trace(go.Scatter(
            x=df_master["quarter"],
            y=df_master["cng_volume_mmscmd"],
            mode="lines+markers",
            name="Actual Sales (Real)",
            line=dict(color="#0f172a", width=3.5),
            marker=dict(size=8, color="#0f172a")
        ))

        # Model backtest series
        fig.add_trace(go.Scatter(
            x=df_results["quarter"],
            y=df_results["ridge_regression"],
            mode="lines+markers",
            name="Winning Ridge (Lag-1 + Fleet)",
            line=dict(color="#10b981", width=2.5, dash="dash"),
            marker=dict(size=6, color="#10b981")
        ))

        fig.add_trace(go.Scatter(
            x=df_results["quarter"],
            y=df_results["naive"],
            mode="lines",
            name="Naive Lag-1 Baseline",
            line=dict(color="#64748b", width=1.8, dash="dot")
        ))

        fig.add_trace(go.Scatter(
            x=df_results["quarter"],
            y=df_results["linear_3feat"],
            mode="lines",
            name="Linear OLS (Lag-1 + Fleet + Price Ratio)",
            line=dict(color="#f59e0b", width=1.8, dash="dot")
        ))

        # Add Q2 FY27 Forecast Point and Interval
        fig.add_trace(go.Scatter(
            x=["Q1 FY27", "Q2 FY27"],
            y=[3.76, ridge_q2["point_forecast_mmscmd"]],
            mode="lines+markers",
            name="Q2 FY27 Forecast",
            line=dict(color="#0066cc", width=3, dash="dash"),
            marker=dict(size=11, color="#0066cc", symbol="star")
        ))

        # Error bar on Q2 FY27
        fig.add_trace(go.Scatter(
            x=["Q2 FY27", "Q2 FY27"],
            y=[ridge_q2["lower_80_mmscmd"], ridge_q2["upper_80_mmscmd"]],
            mode="lines",
            name="80% Forecast Interval",
            line=dict(color="#0066cc", width=4)
        ))

        fig.update_layout(
            height=460,
            margin=dict(l=40, r=40, t=20, b=40),
            xaxis=dict(title="Quarter", tickangle=-45, showgrid=True, gridcolor="#f1f5f9"),
            yaxis=dict(title="CNG Sales Volume (mmscmd)", showgrid=True, gridcolor="#f1f5f9", range=[0.5, 4.3]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            plot_bgcolor="white"
        )
        st.plotly_chart(fig, use_container_width=True)

        # Model Error Comparison Table
        st.markdown("### Walk-Forward Backtest Accuracy Metrics (10 Out-of-Sample Quarters)")
        st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    render_footer()


# ==============================================================================
# PAGE 3: SPACING ANALYSIS
# ==============================================================================
elif page_selection == "3. Station spacing":
    st.title("Station Spacing")
    st.subheader("Spacing thresholds under an assumed catchment radius")
    render_page_badges(["MODELLED", "ASSUMPTION"])

    df_summary = load_spacing_summary()
    df_pairs = load_spacing_results()
    df_stations = load_stations_geocoded()

    if df_summary.empty or df_pairs.empty or df_stations.empty:
        st.error("Spacing data files could not be loaded from data/processed/.")
    else:
        st.markdown(
            "*(Geographic demand overlap under an assumed catchment radius; not an observed sales effect.)*",
            help="Thresholds represent the geographic distance at which two circular population catchments share less than a given percentage of population."
        )

        # Control Filters (Urban mode only)
        f1, f2 = st.columns([1.5, 2.5])
        with f1:
            sel_city = st.selectbox("Select Target City", ["Surat", "Rajkot"], index=0)
        with f2:
            avail_radii = [1.5, 2.0, 2.5, 3.0]
            sel_radius = st.selectbox("Assumed Catchment Radius (R, km)", avail_radii, index=1)
        sel_env = "urban"

        # Spacing Threshold Metrics for selected configuration
        st_rows = df_summary[
            (df_summary["city"] == sel_city)
            & (df_summary["environment"] == sel_env)
            & (df_summary["radius_km"] == sel_radius)
        ].sort_values("overlap_threshold_pct", ascending=False)

        st.markdown(f"### Spacing thresholds under an assumed catchment radius ({sel_city}, R = {sel_radius} km)")
        
        m_cols = st.columns(3)
        threshold_tags = [30, 20, 10]
        for idx, t_pct in enumerate(threshold_tags):
            row_match = st_rows[st_rows["overlap_threshold_pct"] == t_pct]
            if not row_match.empty:
                r = row_match.iloc[0]
                with m_cols[idx]:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">{t_pct}% Overlap Threshold</div>
                        <div class="metric-value">{r['spacing_straight_km']:.2f} km</div>
                        <div style="font-size: 13.5px; color: #475569; font-weight: 600;">
                            Road Equivalent: <strong>{r['spacing_road_km']:.2f} km</strong>
                        </div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 4px;">
                            90% Bootstrap CI: [{r['ci90_p5_straight_km']:.2f}, {r['ci90_p95_straight_km']:.2f}] km straight
                            <br>Multiplier: {r['multiple_k']:.2f} × R
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        st.caption("Road distance assumes a 1.28 circuity factor (Ballou et al. 2002 logistics benchmark range 1.2–1.4) [ASSUMPTION].")

        # Layout: Overlap vs Distance Plot and Interactive Station Map
        col_plot, col_map = st.columns([1.1, 1.0])

        with col_plot:
            st.markdown(f"#### Pairwise Overlap vs. Distance (R = {sel_radius} km)")
            city_pairs = df_pairs[
                (df_pairs["city"] == sel_city)
                & (df_pairs["radius_km"] == sel_radius)
                & (df_pairs["environment"] == sel_env)
            ]

            if city_pairs.empty:
                st.info("No pairwise data available for this combination.")
            else:
                fig_ov = px.scatter(
                    city_pairs,
                    x="distance_straight_km",
                    y="overlap_share",
                    color="overlap_share",
                    color_continuous_scale="Viridis",
                    labels={"distance_straight_km": "Straight-line Separation (km)", "overlap_share": "Catchment Overlap Share"},
                    hover_data=["station_a", "station_b", "distance_road_km"]
                )

                # Add horizontal reference lines for 30%, 20%, 10%
                fig_ov.add_hline(y=0.30, line_dash="dash", line_color="#f59e0b", annotation_text="30% Overlap")
                fig_ov.add_hline(y=0.20, line_dash="dash", line_color="#ef4444", annotation_text="20% Threshold")
                fig_ov.add_hline(y=0.10, line_dash="dash", line_color="#10b981", annotation_text="10% Overlap")

                fig_ov.update_layout(
                    height=450,
                    margin=dict(l=30, r=20, t=10, b=30),
                    plot_bgcolor="white",
                    xaxis=dict(showgrid=True, gridcolor="#f1f5f9"),
                    yaxis=dict(showgrid=True, gridcolor="#f1f5f9", tickformat=".0%"),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_ov, use_container_width=True)

        with col_map:
            st.markdown(f"#### Verified Operating Stations Map ({sel_city})")
            
            # Filter strictly to reliable unique stations for the selected city
            rel_stations = df_stations[
                (df_stations["city"] == sel_city)
                & (df_stations["is_reliable"] == True)
            ].copy()

            if rel_stations.empty:
                st.warning(f"No verified reliable stations found for {sel_city}.")
            else:
                center_lat = rel_stations["lat"].mean()
                center_lon = rel_stations["lon"].mean()

                # Build Folium map with OpenStreetMap tiles
                m = folium.Map(
                    location=[center_lat, center_lon],
                    zoom_start=11,
                    tiles="OpenStreetMap"
                )

                # Draw buffer circles and station pins
                buf_meters = float(sel_radius) * 1000.0
                for _, stn in rel_stations.iterrows():
                    # 2.0 km Catchment circle
                    folium.Circle(
                        location=[stn["lat"], stn["lon"]],
                        radius=buf_meters,
                        color="#0066cc",
                        weight=1.5,
                        fill=True,
                        fill_color="#0066cc",
                        fill_opacity=0.12,
                        tooltip=f"Catchment ({sel_radius} km)"
                    ).add_to(m)

                    # Station marker
                    folium.Marker(
                        location=[stn["lat"], stn["lon"]],
                        popup=folium.Popup(f"<b>{stn['station_name']}</b><br>{stn['address']}<br>Confidence: {stn['confidence']}", max_width=250),
                        tooltip=stn["station_name"],
                        icon=folium.Icon(color="blue", icon="gas-pump", prefix="fa")
                    ).add_to(m)

                st_folium(m, height=450, use_container_width=True)
                st.caption(f"Showing {len(rel_stations)} verified stations with unique coordinates in {sel_city}. Map data (c) OpenStreetMap contributors.")

    render_footer()


# ==============================================================================
# PAGE 4: COVERAGE GAPS & SITING (ILLUSTRATIVE)
# ==============================================================================
elif page_selection == "4. Coverage gaps (illustrative)":
    st.title("Coverage Gaps & Candidate Site Prioritization")
    st.subheader("Audited Municipal Grid Evaluation & Priority Siting")
    render_page_badges(["MODELLED", "ASSUMPTION"])

    render_notice_banner(
        "Illustrative. Only 44 of 136 geocoded stations have verified coordinates. Candidate sites are evaluated on a 500 m municipal grid passing land-use filters and dual-tier exclusion zones. Not validated against proprietary retail sales telemetry.",
        banner_type="warning"
    )

    df_ranked = load_ranked_sites()
    df_stations = load_stations_geocoded()

    if df_ranked.empty or df_stations.empty:
        st.error("Ranked sites data could not be loaded from data/processed/ranked_sites.csv.")
    else:
        # City Filter
        sel_city = st.selectbox("Target Municipal Area", ["Surat", "Rajkot"], index=0, key="gap_city")

        city_ranked = df_ranked[df_ranked["city"] == sel_city].copy()
        display_ranked = city_ranked.sort_values("rank").head(10).reset_index(drop=True)

        # Map and Table side by side
        col_map, col_tbl = st.columns([1.1, 1.1])

        with col_map:
            st.markdown(f"#### Top 10 Candidate Siting Locations ({sel_city})")
            
            # Station subsets
            rel_stns = df_stations[(df_stations["city"] == sel_city) & (df_stations["is_reliable"] == True)]

            m_lat = display_ranked["lat"].mean()
            m_lon = display_ranked["lon"].mean()

            m_siting = folium.Map(location=[m_lat, m_lon], zoom_start=11, tiles="OpenStreetMap")

            # Draw reliable station markers & 2.0 km buffers
            for _, r in rel_stns.iterrows():
                folium.Circle(
                    location=[r["lat"], r["lon"]],
                    radius=2000.0,
                    color="#0066cc",
                    weight=1.2,
                    fill=True,
                    fill_color="#0066cc",
                    fill_opacity=0.08,
                    tooltip=f"Verified Operating: {r['station_name']}"
                ).add_to(m_siting)
                folium.CircleMarker(
                    location=[r["lat"], r["lon"]],
                    radius=4,
                    color="#0066cc",
                    fill=True,
                    fill_color="#0066cc",
                    popup=r["station_name"]
                ).add_to(m_siting)

            # Draw numbered candidate markers 1 to 10
            for _, cand in display_ranked.iterrows():
                rnk = int(cand["rank"])
                
                # Candidate catchment
                folium.Circle(
                    location=[cand["lat"], cand["lon"]],
                    radius=2000.0,
                    color="#10b981",
                    weight=1.8,
                    fill=True,
                    fill_color="#10b981",
                    fill_opacity=0.2,
                    tooltip=f"Candidate #{rnk} Catchment (2.0 km)"
                ).add_to(m_siting)

                # Numbered Marker with rank hover tooltip
                folium.Marker(
                    location=[cand["lat"], cand["lon"]],
                    popup=folium.Popup(
                        f"<b>Candidate Site #{rnk}</b><br>"
                        f"Nearest Station: {cand['nearest_station_km']:.2f} km<br>"
                        f"Overlap: {cand['overlap_share']*100:.1f}%<br>"
                        f"Coverage Gap Score: {cand['score']:.1f}",
                        max_width=220
                    ),
                    tooltip=f"Rank #{rnk}",
                    icon=folium.DivIcon(
                        html=f"""<div style="
                            background-color: #10b981;
                            color: #ffffff;
                            font-weight: 700;
                            font-size: 11px;
                            width: 22px;
                            height: 22px;
                            border-radius: 50%;
                            border: 2px solid #ffffff;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            text-align: center;
                            line-height: 18px;
                        ">{rnk}</div>""",
                        icon_size=(22, 22),
                        icon_anchor=(11, 11)
                    )
                ).add_to(m_siting)

            st_folium(m_siting, height=520, use_container_width=True)
            st.caption("Numbered markers (1–10): Candidate sites ranked by coverage gap | Blue circles: Existing verified operating stations (2.0 km catchments). Map data (c) OpenStreetMap contributors.")

        with col_tbl:
            st.markdown(f"#### Priority Siting Portfolio Data ({sel_city})")
            
            # Format display dataframe without absolute unserved pop or implied density
            table_show = pd.DataFrame({
                "Rank": display_ranked["rank"].astype(int),
                "Location": [f"{r.lat:.4f}, {r.lon:.4f}" for _, r in display_ranked.iterrows()],
                "Nearest Stn (km)": display_ranked["nearest_station_km"].apply(lambda v: f"{v:.2f}"),
                "Overlap (%)": display_ranked["overlap_share"].apply(lambda v: f"{v*100:.1f}%"),
                "Coverage Gap Score": display_ranked["score"].apply(lambda v: f"{v:.1f}")
            })

            st.dataframe(table_show, use_container_width=True, hide_index=True)
            st.caption("Relative coverage-gap ranking from WorldPop 1 km data; illustrative, not validated; absolute population is not shown because the raster is too coarse at 2 km.")

            st.markdown("""
            **Portfolio Notes:**
            - **Coverage Gap Score**: Relative index (0–100) indicating potential demand outside operating station catchments.
            - **Buffer Area**: Standard 2.0 km circular catchment buffer covers 12.57 km2.
            - **Separation**: Evaluated against operating stations under assumed 2.0 km radius.
            """)

        # Optional Stretch: Fast What-If Location Evaluator
        with st.expander("🔍 Interactive 'What-If' Candidate Site Evaluator (Optional Stretch)"):
            st.markdown("""
            Test any arbitrary latitude and longitude in Surat or Rajkot against the precomputed spacing constraint and nearest operating station distance:
            """)
            wi1, wi2, wi3 = st.columns([1.5, 1.5, 1.5])
            with wi1:
                test_city = st.selectbox("City Context", ["Surat", "Rajkot"], index=0, key="wi_city")
            with wi2:
                default_lat = 21.1433 if test_city == "Surat" else 22.2171
                test_lat = st.number_input("Candidate Latitude (°N)", value=default_lat, format="%.5f")
            with wi3:
                default_lon = 72.7439 if test_city == "Surat" else 70.8029
                test_lon = st.number_input("Candidate Longitude (°E)", value=default_lon, format="%.5f")

            # Fast evaluation using distance formula
            c_stns = df_stations[(df_stations["city"] == test_city) & (df_stations["is_reliable"] == True)]
            if not c_stns.empty:
                # Approximate metric distance (1 deg lat ~ 111 km, 1 deg lon ~ 103 km at lat 21)
                lat_scale = 111.0
                lon_scale = 111.0 * np.cos(np.radians(test_lat))
                dists_km = np.sqrt(
                    ((c_stns["lat"] - test_lat) * lat_scale) ** 2
                    + ((c_stns["lon"] - test_lon) * lon_scale) ** 2
                )
                min_d = float(dists_km.min())
                nearest_stn_name = c_stns.iloc[dists_km.argmin()]["station_name"]
                
                req_spacing = 3.11 if test_city == "Surat" else 3.07
                spacing_ok = min_d >= req_spacing

                wi_res1, wi_res2, wi_res3 = st.columns(3)
                with wi_res1:
                    st.metric("Nearest Verified Station", f"{min_d:.2f} km", delta=f"{min_d - req_spacing:+.2f} km vs threshold")
                with wi_res2:
                    st.metric("Minimum Spacing Status", "PASSED ✓" if spacing_ok else "VIOLATION ⚠️", delta="Outside minimum spacing" if spacing_ok else "Inside minimum spacing")
                with wi_res3:
                    st.metric("Nearest Station Name", nearest_stn_name)
                    
                st.caption(f"Nearest station: {nearest_stn_name}. Required spacing threshold for 20% overlap: {req_spacing} km. Only the 44 verified stations are checked.")

    render_footer()


# ==============================================================================
# PAGE 5: EV SCENARIOS
# ==============================================================================
elif page_selection == "5. EV scenarios":
    st.title("Electric Vehicle Diffusion & Fleet Scenarios")
    st.subheader("Policy-Aligned S-Curve Multipliers & 2026–2035 Demand Trajectories")
    render_page_badges(["SOURCED", "ASSUMPTION", "MODELLED"])

    df_ev = load_ev_scenarios()

    if df_ev.empty:
        st.error("EV scenarios data could not be loaded from data/processed/ev_scenarios.csv.")
    else:
        # NITI Aayog Source Banner
        st.markdown(f"""
        <div style="background-color: #f5f3ff; border-left: 4px solid #6366f1; padding: 12px 18px; border-radius: 4px; margin-bottom: 18px; color: #3730a3; font-size: 13.5px; line-height: 1.5;">
            <strong>{badge_html('SOURCED')} NITI Aayog (2021) Official Policy Baseline:</strong><br>
            <em>"The transition to electric vehicles (EVs) in India is targeted to reach 80% sales penetration for two- and three-wheelers, 70% for commercial cars, 40% for buses, and 30% for private cars by 2030."</em>
            <br><span style="font-size: 12px; color: #6b7280;">— NITI Aayog & RMI (2021), <em>Mobilising Electric Vehicle Financing in India</em>, p. 12.</span>
            <br><strong>Distinction:</strong> These are <strong>sales-share targets</strong>. We convert them to <strong>on-road fleet share ceilings</strong> via vehicle stock turnover lags {badge_html('ASSUMPTION')} (8-yr life for 3W, 10-yr for 4W, 12-yr for buses).
        </div>
        """, unsafe_allow_html=True)

        # Normalization Rule Callout & Note
        st.markdown(f"""
        <div style="background-color: #ecfdf5; border: 1px solid #10b981; border-radius: 6px; padding: 12px 16px; margin-bottom: 20px; font-size: 13px; color: #065f46; line-height: 1.5;">
            <strong>Multiplier Normalization:</strong> All scenario multipliers are normalized to identically <strong>1.0000 in 2026</strong> (divided by 2026 raw multiplier), ensuring all trajectories start from the exact observed Q1 FY27 volume of <strong>3.760 mmscmd</strong>.
            <br><em>2026 starting EV shares differ by scenario (ASSUMPTION); demand multipliers are normalised so all scenarios begin from the observed 3.76 mmscmd.</em>
        </div>
        """, unsafe_allow_html=True)

        # Plotly Demand Trajectory Chart
        st.markdown("### Projected GGCL Network CNG Demand (2026–2035)")
        st.caption("Normalized trajectories starting from 3.760 mmscmd in 2026 vs. 4.0% CAGR Counterfactual ICE Growth [ASSUMPTION]")

        fig_ev = go.Figure()

        # Counterfactual ICE line
        cf_years = df_ev[df_ev["scenario"] == "Medium EV"]["year"]
        cf_demand = df_ev[df_ev["scenario"] == "Medium EV"]["counterfactual_demand_mmscmd"]

        fig_ev.add_trace(go.Scatter(
            x=cf_years,
            y=cf_demand,
            mode="lines",
            name="Counterfactual ICE (4.0% CAGR)",
            line=dict(color="#0f172a", width=3, dash="dot")
        ))

        colors = {"Low EV": "#10b981", "Medium EV": "#f59e0b", "High EV": "#ef4444"}
        for sc in ["Low EV", "Medium EV", "High EV"]:
            sc_sub = df_ev[df_ev["scenario"] == sc]
            fig_ev.add_trace(go.Scatter(
                x=sc_sub["year"],
                y=sc_sub["projected_cng_demand_mmscmd"],
                mode="lines+markers",
                name=f"{sc} Scenario",
                line=dict(color=colors[sc], width=2.5),
                marker=dict(size=6)
            ))

        fig_ev.update_layout(
            height=430,
            margin=dict(l=40, r=40, t=15, b=40),
            xaxis=dict(title="Year", tickmode="linear", tick0=2026, dtick=1, showgrid=True, gridcolor="#f1f5f9"),
            yaxis=dict(title="Network CNG Sales (mmscmd)", showgrid=True, gridcolor="#f1f5f9", range=[2.5, 5.8]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            plot_bgcolor="white"
        )
        st.plotly_chart(fig_ev, use_container_width=True)

        # 2030 Impact Summary Metrics
        st.markdown("### 2030 Horizon Impact Comparison")
        ev2030 = df_ev[df_ev["year"] == 2030]
        
        c_low, c_med, c_high = st.columns(3)
        for c_box, sc_name in zip([c_low, c_med, c_high], ["Low EV", "Medium EV", "High EV"]):
            row_sc = ev2030[ev2030["scenario"] == sc_name].iloc[0]
            pct_vs_cf = ((row_sc["projected_cng_demand_mmscmd"] - row_sc["counterfactual_demand_mmscmd"]) / row_sc["counterfactual_demand_mmscmd"]) * 100.0
            pct_vs_base = ((row_sc["projected_cng_demand_mmscmd"] - 3.760) / 3.760) * 100.0
            with c_box:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">{sc_name} (2030)</div>
                    <div class="metric-value">{row_sc['projected_cng_demand_mmscmd']:.3f} mmscmd</div>
                    <div style="font-size: 13.5px; color: {colors[sc_name]}; font-weight: 700;">
                        {pct_vs_cf:.1f}% vs ICE Counterfactual ({row_sc['counterfactual_demand_mmscmd']:.2f} mmscmd)
                    </div>
                    <div style="font-size: 12px; color: #64748b; margin-top: 4px;">
                        Multiplier: {row_sc['cng_demand_multiplier']:.4f} | EV Fleet Share: {row_sc['ev_fleet_share']*100:.1f}%
                        <br>{pct_vs_base:+.1f}% net change vs 2026 actual base (3.76 mmscmd)
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # Parameter Table (Segment S-curve chart removed per requirements)
        st.markdown("### Scenario Assumptions & Source Provenance")
        raw_params = [
            {
                "Parameter": "3W 2030 Sales Target",
                "Medium Value": "80%",
                "Medium Tag": "SOURCED",
                "High Value": "95%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Medium (80%) from NITI Aayog (2021) p. 12; High (95%) is ASSUMPTION"
            },
            {
                "Parameter": "3W Operational Lifetime",
                "Medium Value": "8 Years",
                "Medium Tag": "ASSUMPTION",
                "High Value": "7 Years",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "analyst assumption, no source"
            },
            {
                "Parameter": "3W Fleet Ceiling (L)",
                "Medium Value": "55%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "70%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Derived from 80% sales target with 8-yr turnover lag"
            },
            {
                "Parameter": "4W Commercial Cab Sales",
                "Medium Value": "70%",
                "Medium Tag": "SOURCED",
                "High Value": "100%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Medium (70%) from NITI Aayog (2021) p. 12; High (100%) is ASSUMPTION"
            },
            {
                "Parameter": "4W Private Car Sales",
                "Medium Value": "30%",
                "Medium Tag": "SOURCED",
                "High Value": "40%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Medium (30%) from NITI Aayog (2021) p. 12; High (40%) is ASSUMPTION"
            },
            {
                "Parameter": "4W Operational Lifetime",
                "Medium Value": "10 Years",
                "Medium Tag": "ASSUMPTION",
                "High Value": "10 Years",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "analyst assumption, no source"
            },
            {
                "Parameter": "4W Fleet Ceiling (L)",
                "Medium Value": "25%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "40%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Derived from composite 40% sales target with 10-yr turnover lag"
            },
            {
                "Parameter": "Bus 2030 Sales Target",
                "Medium Value": "40%",
                "Medium Tag": "SOURCED",
                "High Value": "75%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Medium (40%) from NITI Aayog (2021) p. 12; High (75%) is ASSUMPTION"
            },
            {
                "Parameter": "Bus Operational Lifetime",
                "Medium Value": "12 Years",
                "Medium Tag": "ASSUMPTION",
                "High Value": "10 Years",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "analyst assumption, no source"
            },
            {
                "Parameter": "Bus Fleet Ceiling (L)",
                "Medium Value": "28%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "45%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Derived from 40% sales target with 12-yr municipal replacement"
            },
            {
                "Parameter": "CNG Demand Weight (3W)",
                "Medium Value": "50%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "50%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Estimated retail CNG volume share in Gujarat CGDs"
            },
            {
                "Parameter": "CNG Demand Weight (4W)",
                "Medium Value": "35%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "35%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Estimated retail CNG volume share in Gujarat CGDs"
            },
            {
                "Parameter": "CNG Demand Weight (Bus)",
                "Medium Value": "15%",
                "Medium Tag": "ASSUMPTION",
                "High Value": "15%",
                "High Tag": "ASSUMPTION",
                "Citation / Note": "Estimated retail CNG volume share in Gujarat CGDs"
            }
        ]

        display_params = []
        for p in raw_params:
            display_params.append({
                "Parameter": p["Parameter"],
                "Medium Value": f"{p['Medium Value']} {badge_html(p['Medium Tag'])}",
                "High Value": f"{p['High Value']} {badge_html(p['High Tag'])}",
                "Citation / Note": p["Citation / Note"]
            })

        params_df = pd.DataFrame(display_params)
        st.write(
            params_df.to_html(escape=False, index=False),
            unsafe_allow_html=True
        )

    render_footer()


# ==============================================================================
# PAGE 6: LIMITATIONS & DATA INGESTION ROADMAP
# ==============================================================================
elif page_selection == "6. Limitations and next steps":
    st.title("Methodological Limitations & Next Steps")
    st.subheader("Transparent Audit, Data Deficits, and Ingestion Roadmap")
    render_page_badges(["REAL", "MODELLED", "ASSUMPTION"])

    # Limitations List
    st.markdown("### Documented Methodological Limitations")
    st.markdown("""
    In strict compliance with challenge guidelines, all analytical boundaries and known data deficits are transparently documented:
    """)

    l1, l2 = st.columns(2)
    with l1:
        st.markdown(r"""
        1. **Proprietary Station-Level Sales Data**:
           - **Limitation**: GGCL's station-level dispenser sales telemetry is proprietary. All candidate scores rely on **unserved population proxies** from the WorldPop 2020 raster rather than observed cash-register sales.
           - **Consequence**: Scores indicate relative geographic demand exposure, not guaranteed commercial dispenser throughput.
        
        2. **20% Station Leave-Out Sanity Test (0.0% Recovery)**:
           - **Limitation**: When 20% of verified stations were removed across 5 random seeds (`[42, 101, 777, 2023, 9999]`), the mean recovery rate of removed station areas in the Top 10 candidate set was **0.0% in both Surat and Rajkot**.
           - **Diagnosis**: Conservative $d_{\min} + 1.5 \text{ km} \approx 4.6 \text{ km}$ exclusion zones around the 92 approximate/pincode-centroid stations blanket the central core. Removing verified stations cannot open up core cells because approximate stations block them. The algorithm correctly routes all candidate capacity to unconstrained peripheral growth corridors.
        
        3. **Statewide vs. District-Level VAHAN Registrations**:
           - **Limitation**: VAHAN registrations are currently aggregated at the Gujarat statewide level. RTO-specific series for Surat (`GJ-05`, `GJ-28`) and Rajkot (`GJ-03`, `GJ-36`) have not yet been isolated into separate local features.
        """)

    with l2:
        st.markdown(f"""
        4. **Buffer-Based Planar Catchments vs. Road Networks**:
           - **Limitation**: Road network isolines could not be generated due to Overpass API rate limits and network timeouts. Catchments are circular metric buffers (UTM Zone 43N).
           - **Assumptions**: The 1.28 circuity factor and 25 km/h urban travel speed are published transportation benchmarks {badge_html('ASSUMPTION')}, not measured telemetry.
        
        5. **Geocoding Precision Deficit**:
           - **Limitation**: Only 44 stations (32.4% of geocoded entries) possess verified high/medium confidence unique coordinates. 92 stations have approximate coordinates or pincode centroids.
           - **Consequence**: All candidate site locations must be treated as **illustrative** until ground-truth GPS coordinates are verified.
        
        6. **Competitor Proximity Incompleteness**:
           - **Limitation**: OpenStreetMap contains only 2 competitor stations near Surat and 2 near Rajkot (~1% network coverage). Competitor proximity is reported purely as an illustrative proof-of-concept.
        """, unsafe_allow_html=True)

    st.markdown("---")

    # GGCL Enterprise Data Ingestion Roadmap
    st.markdown("### GGCL Enterprise Data Ingestion Roadmap")
    st.markdown("""
    The entire pipeline is designed to accept GGCL's proprietary station telemetry. Once GGCL provides its internal station records, drop the CSV file into `data/raw/ggcl_station_sales.csv`:
    """)

    # Expected CSV Schema
    schema_df = pd.DataFrame([
        {"Column Name": "station_id", "Data Type": "STRING", "Required": "YES", "Example": "GGL-SRT-0142", "Description": "Unique internal retail station identifier"},
        {"Column Name": "station_name", "Data Type": "STRING", "Required": "YES", "Example": "Adajan CNG Station", "Description": "Official station trade name"},
        {"Column Name": "latitude", "Data Type": "FLOAT", "Required": "YES", "Example": "21.19421", "Description": "WGS84 GPS coordinate (precision ≥ 5 decimals)"},
        {"Column Name": "longitude", "Data Type": "FLOAT", "Required": "YES", "Example": "72.79314", "Description": "WGS84 GPS coordinate (precision ≥ 5 decimals)"},
        {"Column Name": "city", "Data Type": "STRING", "Required": "YES", "Example": "Surat", "Description": "Geographical Area (Surat, Rajkot, etc.)"},
        {"Column Name": "quarter", "Data Type": "STRING", "Required": "YES", "Example": "Q1 FY26", "Description": "Quarter identifier matching master table"},
        {"Column Name": "cng_sales_volume_kg", "Data Type": "FLOAT", "Required": "YES", "Example": "342150.0", "Description": "Quarterly metered retail CNG sales in kilograms"},
        {"Column Name": "cng_sales_volume_scm", "Data Type": "FLOAT", "Required": "OPTIONAL", "Example": "451638.0", "Description": "Standard cubic meters equivalent"},
        {"Column Name": "dispenser_count", "Data Type": "INTEGER", "Required": "YES", "Example": "4", "Description": "Active physical dispensing nozzles"},
        {"Column Name": "compressor_capacity_kg_hr", "Data Type": "FLOAT", "Required": "OPTIONAL", "Example": "1200.0", "Description": "Compressor rated capacity for queue modeling"}
    ])
    st.dataframe(schema_df, use_container_width=True, hide_index=True)

    # Workflow Steps
    st.markdown(r"""
    #### Planned Processing Workflow Upon Ingestion
    ```bash
    # 1. Place proprietary export in raw data folder
    cp ggcl_station_sales_2026.csv data/raw/ggcl_station_sales.csv

    # 2. Run automated pipeline (substitutes population proxy with real sales calibration)
    python src/features/build_master_table.py --with-station-sales
    python src/spacing/catchment_overlap.py --calibrate-cannibalisation
    python src/siting/rank_sites.py --target-revenue
    ```
    - **Step 1: Ground-Truth Calibration**: The spacing model replaces geographic population overlap with an empirical revenue cannibalization regression ($\Delta \text{Sales}_i = f(\text{Distance}_{ij}, \text{Sales}_j)$).
    - **Step 2: Queue & Peak Congestion**: Dispensers and compressor ratings unlock the hourly queue delay simulator, prioritizing relief stations near congested nodes.
    - **Step 3: Financial ROI**: Candidate scores convert directly into projected payback periods and internal rate of return (IRR).
    """)

    render_footer()
