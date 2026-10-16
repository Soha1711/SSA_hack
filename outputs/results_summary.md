# Results summary (single source of truth for slides and README)

- Forecast error, baseline: 3.35% MAPE / 0.121 mmscmd RMSE (Naive lag-1)
- Forecast error, model: 1.76% MAPE / 0.079 mmscmd RMSE (Standardized Ridge, lag-1 + fleet proxy)
- Spacing analysis rule (buffer-based catchments):
  - **Urban catchments** (under assumed catchment radius $R \in [1.5, 3.0]$ km; baseline $R = 2.0$ km):
    - Overlap falls below 30% at about $1.37 – 1.51 \times R$ ($2.73$ km straight-line / $3.50$ km road in Surat [90% CI: 2.61 – 2.85 km]; $3.02$ km straight / $3.86$ km road in Rajkot [90% CI: 2.62 – 3.32 km])
    - Overlap falls below 20% at about $1.53 – 1.55 \times R$ ($3.11$ km straight-line / $3.98$ km road in Surat [90% CI: 2.85 – 3.15 km]; $3.07$ km straight / $3.92$ km road in Rajkot [90% CI: 2.91 – 3.61 km])
    - Overlap falls below 10% at about $1.59 – 1.67 \times R$ ($3.19$ km straight-line / $4.08$ km road in Surat [90% CI: 3.06 – 3.54 km]; $3.34$ km straight / $4.27$ km road in Rajkot [90% CI: 3.19 – 4.00 km])
  - **Corridor catchments** (under assumed catchment radius $R \in [4.0, 8.0]$ km; baseline $R = 6.0$ km):
    - Overlap falls below 30% at about $1.52 – 1.73 \times R$ ($10.41$ km straight-line / $13.32$ km road in Surat [90% CI: 7.35 – 10.82 km]; $9.12$ km straight / $11.68$ km road in Rajkot [90% CI: 8.68 – 10.31 km])
    - Overlap falls below 20% at about $1.78 – 1.81 \times R$ ($10.88$ km straight-line / $13.93$ km road in Surat [90% CI: 9.19 – 11.08 km]; $10.65$ km straight / $13.64$ km road in Rajkot [90% CI: 9.15 – 10.96 km])
    - Overlap falls below 10% at about $1.84 – 1.86 \times R$ ($11.14$ km straight-line / $14.26$ km road in Surat [90% CI: 9.88 – 11.31 km]; $11.04$ km straight / $14.13$ km road in Rajkot [90% CI: 10.63 – 11.46 km])
- **Methodology & Key Assumptions**:
  - Road-network isolines could NOT be built because Overpass API queries failed under rate limits and network timeouts; catchments are therefore circular planar buffers (UTM Zone 43N).
  - Circuity factor of 1.28 (cited from Ballou et al. 2002 range of 1.2–1.4 for logistics and urban networks) and 25 km/h speed are ASSUMPTIONS, not local road measurements.
  - Spacing thresholds reflect buffer-based geographic demand co-exposure (WorldPop 2020 UN-adjusted population raster), NOT an observed sales drop or measured cannibalisation.
  - Geocoding filtered strictly to 44 high/medium confidence stations with unique coordinates (Surat: 23, Rajkot: 14, Ahmedabad: 6, Vadodara: 1; all pincode centroids and shared-coordinate clusters dropped).
- **Top 5 Candidate Siting Opportunities** (20% overlap spacing constraint from `spacing_summary.csv` [Surat: 3.11 km, Rajkot: 3.07 km]; relative priority scores, NOT demand forecasts):
  - **Surat**:
    1. `Site S-01` (21.1680°N, 72.6675°E): Unserved Pop = 689,307 | Nearest Stn = 3.65 km | Overlap = 0.0% | Score = 100.00 [ROBUST]
    2. `Site S-02` (21.1680°N, 72.6627°E): Unserved Pop = 670,511 | Nearest Stn = 4.11 km | Overlap = 0.0% | Score = 97.27 [ROBUST]
    3. `Site S-03` (21.1725°N, 72.6626°E): Unserved Pop = 651,641 | Nearest Stn = 3.95 km | Overlap = 0.0% | Score = 94.54 [ROBUST]
    4. `Site S-04` (21.1634°N, 72.6627°E): Unserved Pop = 623,676 | Nearest Stn = 4.32 km | Overlap = 0.0% | Score = 90.48
    5. `Site S-05` (21.1735°N, 72.7348°E): Unserved Pop = 600,412 | Nearest Stn = 3.82 km | Overlap = 0.0% | Score = 87.10 [ROBUST]
  - **Rajkot**:
    1. `Site R-01` (22.2533°N, 70.7650°E): Unserved Pop = 76,167 | Nearest Stn = 3.65 km | Overlap = 0.0% | Score = 85.68
    2. `Site R-02` (22.2532°N, 70.7601°E): Unserved Pop = 59,763 | Nearest Stn = 3.78 km | Overlap = 0.0% | Score = 78.46
    3. `Site R-03` (22.2575°N, 70.7503°E): Unserved Pop = 56,842 | Nearest Stn = 3.79 km | Overlap = 0.0% | Score = 74.63
    4. `Site R-04` (22.2577°N, 70.7600°E): Unserved Pop = 71,607 | Nearest Stn = 3.31 km | Overlap = 16.9% | Score = 69.74
    5. `Site R-05` (22.2228°N, 70.8046°E): Unserved Pop = 49,623 | Nearest Stn = 4.10 km | Overlap = 0.0% | Score = 65.15
- **EV Scenario Effect on 2030 Demand** (Base 2026 volume = 3.760 mmscmd [SOURCED: Q1 FY27 actual]; Counterfactual ICE @ 4% CAGR = 4.399 mmscmd [ASSUMPTION]):
  - **Low EV Adoption**: Multiplier = 0.8488 (EV fleet share 15.12%) -> Projected Demand = 3.733 mmscmd (**-15.1%** vs counterfactual, -0.7% vs 2026 base)
  - **Medium EV Adoption (Baseline)**: Multiplier = 0.7044 (EV fleet share 29.56%) -> Projected Demand = 3.098 mmscmd (**-29.6%** vs counterfactual, -17.6% vs 2026 base)
  - **High EV Adoption**: Multiplier = 0.5272 (EV fleet share 47.28%) -> Projected Demand = 2.319 mmscmd (**-47.3%** vs counterfactual, -38.3% vs 2026 base)
- **Sanity Validation (20% Station Leave-Out Test)**:
  - **Rajkot**: 2/3 (66.7%) removed station areas recovered in top 10 candidates (National Automobiles recovered within 0.24 km, RCT Police Welfare within 0.79 km).
  - **Surat**: 0/5 (0.0%) removed station areas recovered in top 10 candidates. Reason: Surat has a massive southwest whitespace (>680,000 unserved population in the Hazira/Magdalla industrial-urban corridor) whose raw scores dominate the city-wide top 10 regardless of 20% central removals.
- **Robust Siting Portfolio** (Sites remaining in Top 10 across Base, Low, Medium, and High EV under the Urban Density Fleet Resilience Rule):
  - **Surat**: 10 sites robust overall; 6 of the Base Top 10 (#1, #2, #3, #5, #8, #10) maintain Top 10 status across all EV scenarios due to high localized population density (>50,000 persons/km²).
  - **Rajkot**: 5 sites robust overall; Base #9 (22.2179°N, 70.7902°E) plus 4 central core candidates maintain Top 10 status due to dense commercial fleet activity as peripheral demand erodes.

## Appendix: Competitor analysis (illustrative: OSM contains very few competitor stations)
- OSM contains only 2 mapped competitor CNG stations within 30 km of Surat and 2 within 30 km of Rajkot (~1% GGCL coverage baseline across Gujarat).
- In Surat, 6/23 (26.1%) of GG stations intersect a 2.0 km competitor buffer, and 20/23 (87.0%) intersect a 6.0 km corridor competitor buffer.
- In Rajkot, 5/14 (35.7%) intersect a 2.0 km competitor buffer, and 13/14 (92.9%) intersect a 6.0 km corridor competitor buffer.
- Due to volunteer mapping incompleteness, competitor proximity is reported purely for illustrative methodological completeness and should not guide commercial capital allocation without full retail census data.
