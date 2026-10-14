# CNG Demand Planner

Seva First Innovation Challenge 2026 - **PS000002**: Station-Level Demand Forecasting for CNG Sales to Optimize Network Expansion (Gujarat Gas Company Limited).

> Team ID: TM000846 | Demo video: _add link_ | Live app: _add link_

## What it does
1. **Forecast engine** - forecasts CNG demand from real registrations, fuel-price gap and seasonality, with error measured against a baseline.
2. **Spacing analyzer** - uses real station locations and road-network catchments to estimate overlap/cannibalisation and a recommended minimum spacing.
3. **Site ranker** - scores candidate locations on demand potential and coverage gaps, under low / medium / high EV-adoption scenarios.
4. **Peak & queue module (design)** - hourly demand vs capacity framework, ready to take GGCL's station data.

## Data: what is real, what is estimated
| Data | Source | Status |
|---|---|---|
| Station locations | OpenStreetMap | Real (coverage < 100%, see data/DATA_SOURCES.md) |
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
python src/siting/rank_sites.py

streamlit run app/streamlit_app.py
```

## Key results
_Fill from `outputs/results_summary.md` once the models have run._

## Limitations and next steps
- Station-level sales are estimated, not observed; the pipeline accepts a GGCL CSV in the same format.
- The spacing threshold is derived from geographic/demand overlap and must be calibrated on real sales.
- Next: pilot on GGCL data, hourly queue model, network-wide rollout.

## Attribution
Map data (c) OpenStreetMap contributors, ODbL.
