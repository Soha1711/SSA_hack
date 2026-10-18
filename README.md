# CNG Demand Planner

Seva First Innovation Challenge 2026 - **PS000002**: Station-Level Demand Forecasting for CNG Sales to Optimize Network Expansion (Gujarat Gas Company Limited).

> Team ID: TM000846 | GitHub: [Soha1711/SSA_hack](https://github.com/Soha1711/SSA_hack) | Demo video: _add link_ | Live app: _add link_

## What it does
1. **Forecast engine** - forecasts CNG demand from real registrations, fuel-price gap and seasonality, with error measured against a baseline.
2. **Spacing analyzer** - uses verified station locations and buffer-based catchments (with WorldPop 2020 population density) to estimate geographic demand overlap and recommended minimum spacing across multiple assumed catchment radii.
3. **Site ranker** - scores candidate locations on demand potential and coverage gaps, under low / medium / high EV-adoption scenarios.
4. **Peak & queue module (design)** - hourly demand vs capacity framework, ready to take GGCL's station data.

## Data: what is real, what is estimated
| Data | Source | Status |
|---|---|---|
| Station locations | Gujarat Gas official directory + OpenStreetMap | Real (44 high/medium confidence unique stations analyzed; OSM coverage < 100%, see data/DATA_SOURCES.md) |
| CNG vehicle registrations | VAHAN dashboard | Real |
| Fuel prices | Public price records | Real |
| GGCL CNG volumes | GGCL quarterly press releases | Real (network level) |
| Station-level sales | Not public | **Estimated** by a documented allocation model |

## Run it
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python src/data_collection/fetch_osm_stations.py     # writes osm_cng_stations_gujarat.csv (move to data/raw/)
python src/data_collection/clean_vahan.py --file data/raw/vahan/<export>.xlsx --header-row 3 --year 2024
python src/features/build_master_table.py
python src/forecasting/model.py
python src/spacing/catchment_overlap.py
python src/siting/rank_sites.py                      # Module D Part 1: Site ranking & buffer catchments
python src/siting/ev_scenarios.py                    # Module D Part 2: EV S-curves & robust sites
```

### Run the dashboard
Launch the self-contained interactive decision-support application:
```bash
streamlit run app/streamlit_app.py
```
- **Startup Time**: Loads in < 5 seconds; fully self-contained using precomputed datasets with zero external API dependencies.
- **Pages Built**:
  1. **Overview & Data Provenance**: Problem definition (PS000002, GGCL), modular architecture, executive KPIs, and comprehensive dataset lineage catalogue with status badges (`REAL`, `MODELLED`, `ASSUMPTION`, `SOURCED`).
  2. **Network Demand Forecast**: Historical quarterly sales (Q1 FY21 – Q1 FY27), walk-forward backtest comparisons, error ranking (Ridge winning at 1.76% MAPE), and Q2 FY27 official horizon forecast (3.88 mmscmd [80% CI: 3.80–3.97 mmscmd]).
  3. **Buffer Spacing Analysis**: Pairwise overlap vs. distance scatter plots, 30%/20%/10% spacing thresholds across 7 catchment radii (1.5–8.0 km), and verified operating station map on OpenStreetMap tiles.
  4. **Coverage Gaps & Siting (Illustrative)**: Top 10 candidate sites per city with toggle for Urban Density Fleet Resilience Rule, candidate pin map with operating station buffers, and an interactive "What-If" location checker.
  5. **Multi-Segment EV Scenarios**: 2026–2035 demand trajectories normalized to 1.0000 in 2026 (3.760 mmscmd base), 3W/4W/Bus S-curve fleet share breakdowns, and NITI Aayog (2021) p. 12 verbatim target citations.
  6. **Limitations & Data Ingestion Roadmap**: Honest audit of data deficits (0% leave-out recovery, statewide VAHAN, unserved population proxy) and complete enterprise CSV ingestion schema for GGCL proprietary sales data.

## Key results
- **Forecast Error**: Baseline Naive lag-1: 3.35% MAPE / 0.121 mmscmd RMSE; Winning Ridge Model: 1.76% MAPE / 0.079 mmscmd RMSE (Q2 FY27 forecast: 3.88 mmscmd).
- **Spacing Analysis Rule (Buffer-Based Catchments)**:
  - *Urban catchments* (under assumed radius $R = 2.0$ km): overlap falls below 30% at $\sim 1.37 - 1.51 \times R$ (2.7 – 3.0 km straight / 3.5 – 3.9 km road), below 20% at $\sim 1.53 - 1.55 \times R$ (3.1 km straight / 4.0 km road), and below 10% at $\sim 1.59 - 1.67 \times R$ (3.2 – 3.3 km straight / 4.1 – 4.3 km road; 90% bootstrap CI: 3.1 – 4.0 km straight).
  - *Corridor catchments* (under assumed radius $R = 6.0$ km): overlap falls below 30% at $\sim 1.52 - 1.73 \times R$ (9.1 – 10.4 km straight / 11.7 – 13.3 km road), below 20% at $\sim 1.78 - 1.81 \times R$ (10.7 – 10.9 km straight / 13.6 – 13.9 km road), and below 10% at $\sim 1.84 - 1.86 \times R$ (11.0 – 11.1 km straight / 14.1 – 14.3 km road; 90% bootstrap CI: 9.9 – 11.5 km straight).
- **Site-Ranking (Module D Part 1)**:
  - *Data Caveat*: Candidate sites are **illustrative** because only a subset of stations has reliable coordinates (44 unique high/medium confidence stations out of 136 geocoded records). The remaining 92 stations have approximate coordinates or pincode centroids, which are treated conservatively as exclusion zones ($d_{\min} + 1.5$ km) to avoid recommending sites adjacent to operating stations.
  - Search box strictly bounded to municipal urban limits (SMC & RUDA), eliminating coastal marshes and dasymetric anomalies in industrial zones.
  - Enforced land check: population density $\ge 1,000$ pop/km² in cell and in $\ge 5$ of 8 neighboring cells.
  - Enforced 20% overlap minimum spacing constraint from `spacing_summary.csv` (Surat: 3.11 km, Rajkot: 3.07 km).
  - Top candidate sites identified in unserved urban corridors (Surat: South/Southwest urban fringe [Bhatha/Pal/Vesu], ~418k–483k unserved pop, implied densities 33,000–38,400 pop/km²; Rajkot: Western radial corridor, ~16k–44k unserved pop, implied densities 1,270–3,530 pop/km²).
  - Leave-out validation (5 seeds, 20% station removal): Mean recovery is 0.0% in both cities because conservative $4.6$ km exclusion buffers around remaining approximate/pincode stations blanket the core, directing new candidate cells to peripheral expansion corridors.
- **EV Scenario S-Curves & Robust Sites (Module D Part 2)**:
  - Normalization: Multipliers divided by 2026 value, ensuring all scenarios start identically at the observed Q1 FY27 actual volume (3.760 mmscmd).
  - S-curves for 3W, 4W, and Bus segments based on NITI Aayog (2021) p. 12 targets: quoted verbatim as *sales-share targets* (80% 3W, 70% commercial cabs, 40% buses, 30% private cars by 2030) and converted to on-road fleet share ceilings using stock turnover assumptions (`ASSUMPTION`: 8-yr 3W life = 55% ceiling, 10-yr 4W life = 25% ceiling, 12-yr bus life = 28% ceiling).
  - Projected 2030 network demand (Counterfactual ICE @ 4% CAGR = 4.399 mmscmd):
    * Low EV: Multiplier = 0.9199 $\rightarrow$ 4.046 mmscmd (-8.0% vs counterfactual, +7.6% vs 2026 base).
    * Medium EV (Baseline): Multiplier = 0.8305 $\rightarrow$ 3.653 mmscmd (-16.9% vs counterfactual, -2.8% vs 2026 base).
    * High EV: Multiplier = 0.6961 $\rightarrow$ 3.062 mmscmd (-30.4% vs counterfactual, -18.6% vs 2026 base).
  - Urban Density Fleet Resilience Rule evaluates candidate sites that "keep top-10 rank under the assumed density rule" (Surat: 4 sites robust; Rajkot: 8 sites robust, with ranks #1–#5 rock-solid).
  - Both base ranks (without density bonus) and scenario ranks are reported side-by-side for transparent comparison.

## Limitations and next steps
- Candidate sites are **illustrative** because only a subset of stations has reliable coordinates (44/136); 92 approximate/pincode stations were used for conservative exclusion buffers ($d_{\min} + 1.5$ km) but lack retail parcel precision.
- Road-network isolines could not be built because Overpass failed under rate limits and network timeouts; catchments are circular metric buffers (UTM Zone 43N).
- The 1.28 circuity factor (cited from Ballou et al. 2002 range of 1.2–1.4 for logistics and urban networks) and 25 km/h speed are ASSUMPTIONS, not local road measurements.
- Station-level sales are estimated, not observed; the pipeline accepts a GGCL CSV in the same format.
- Spacing results reflect buffer-based geographic demand overlap, NOT an observed sales effect, and must be calibrated against real station sales.
- Competitor analysis is illustrative: OpenStreetMap contains very few competitor stations (~1% of GGCL Gujarat network).
- Next: pilot on GGCL data, hourly queue model, network-wide rollout.

## Attribution
Map data (c) OpenStreetMap contributors, ODbL. Population raster from WorldPop (2020 UN-adjusted 1km).
