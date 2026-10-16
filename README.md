# CNG Demand Planner

Seva First Innovation Challenge 2026 - **PS000002**: Station-Level Demand Forecasting for CNG Sales to Optimize Network Expansion (Gujarat Gas Company Limited).

> Team ID: TM000846 | Demo video: _add link_ | Live app: _add link_

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

streamlit run app/streamlit_app.py
```

## Key results
- **Forecast Error**: Baseline Naive lag-1: 3.35% MAPE / 0.121 mmscmd RMSE; Winning Ridge Model: 1.76% MAPE / 0.079 mmscmd RMSE (Q2 FY27 forecast: 3.88 mmscmd).
- **Spacing Analysis Rule (Buffer-Based Catchments)**:
  - *Urban catchments* (under assumed radius $R = 2.0$ km): overlap falls below 30% at $\sim 1.37 - 1.51 \times R$ (2.7 – 3.0 km straight / 3.5 – 3.9 km road), below 20% at $\sim 1.53 - 1.55 \times R$ (3.1 km straight / 4.0 km road), and below 10% at $\sim 1.59 - 1.67 \times R$ (3.2 – 3.3 km straight / 4.1 – 4.3 km road; 90% bootstrap CI: 3.1 – 4.0 km straight).
  - *Corridor catchments* (under assumed radius $R = 6.0$ km): overlap falls below 30% at $\sim 1.52 - 1.73 \times R$ (9.1 – 10.4 km straight / 11.7 – 13.3 km road), below 20% at $\sim 1.78 - 1.81 \times R$ (10.7 – 10.9 km straight / 13.6 – 13.9 km road), and below 10% at $\sim 1.84 - 1.86 \times R$ (11.0 – 11.1 km straight / 14.1 – 14.3 km road; 90% bootstrap CI: 9.9 – 11.5 km straight).
- **Site-Ranking (Module D Part 1)**:
  - Enforced 20% overlap minimum spacing constraint from `spacing_summary.csv` (Surat: 3.11 km, Rajkot: 3.07 km).
  - Evaluated on regular 500 m grid inside built-up areas ($\ge 1000$ pop/km² [ASSUMPTION]). Relative priority scores based on unserved population share minus overlap penalty.
  - Top candidate sites identified in unserved high-density growth zones (Surat: Southwest industrial/port corridor, >680k unserved pop; Rajkot: Western/Southwestern perimeter, >76k unserved pop).
  - Leave-out validation (20% station removal): Rajkot recovered 66.7% of removed station areas in top 10; Surat recovered 0.0% because the massive southwest unserved whitespace dominates top scores citywide.
- **EV Scenario S-Curves & Robust Sites (Module D Part 2)**:
  - S-curves for 3W, 4W, and Bus segments based on NITI Aayog (2021) 2030 targets and Gujarat EV Policy (2021).
  - Projected 2030 network demand: Low EV = 3.733 mmscmd (-15.1% vs 4% CAGR counterfactual); Medium EV = 3.098 mmscmd (-29.6%); High EV = 2.319 mmscmd (-47.3%).
  - Urban Density Fleet Resilience Rule identifies robust candidate sites maintaining Top 10 status across all EV scenarios (Surat: 10 sites robust overall, 6 from Base top 10; Rajkot: 5 sites robust overall, consolidating around core commercial density).

## Limitations and next steps
- Road-network isolines could not be built because Overpass failed under rate limits and network timeouts; catchments are circular metric buffers (UTM Zone 43N).
- The 1.28 circuity factor (cited from Ballou et al. 2002 range of 1.2–1.4 for logistics and urban networks) and 25 km/h speed are ASSUMPTIONS, not local road measurements.
- Station-level sales are estimated, not observed; the pipeline accepts a GGCL CSV in the same format.
- Spacing results reflect buffer-based geographic demand overlap, NOT an observed sales effect, and must be calibrated against real station sales.
- Competitor analysis is illustrative: OpenStreetMap contains very few competitor stations (~1% of GGCL Gujarat network).
- Next: pilot on GGCL data, hourly queue model, network-wide rollout.

## Attribution
Map data (c) OpenStreetMap contributors, ODbL.
