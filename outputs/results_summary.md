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
- **Candidate Siting Opportunities (Module D Part 1)**:
  - *Data Caveat*: Candidate sites are **illustrative** because only a subset of stations has reliable coordinates (44 unique high/medium confidence stations out of 136 geocoded records). The remaining 92 stations have approximate coordinates or pincode centroids, which are treated conservatively as exclusion zones ($d_{\min} + 1.5$ km) to avoid recommending sites right next to existing stations, but whose true retail locations are uncertain.
  - Enforced 20% overlap minimum spacing constraint from `spacing_summary.csv` (Surat: 3.11 km, Rajkot: 3.07 km).
  - Search box strictly bounded to municipal urban limits (SMC: 72.74–72.93°E, 21.08–21.28°N; RUDA: 70.65–70.90°E, 22.15–22.42°N), eliminating coastal marshlands and Hazira heavy-industrial dasymetric anomalies.
  - Land check enforced: raster density $\ge 1,000$ pop/km² in the candidate cell AND in $\ge 5$ of its 8 neighboring cells.
  - Scores are relative priority scores based on unserved population share minus overlap penalty, NOT sales forecasts.
  - **Surat Top 5 Candidates**:
    1. `Site S-01` (21.1433°N, 72.7439°E): Unserved Pop = 482,673 | Nearest Stn = 6.33 km | Implied Density = 38,410 pop/km² | Score = 100.00 [drops out of top-10 under assumed density rule; Rank #11 under High EV]
    2. `Site S-02` (21.1478°N, 72.7438°E): Unserved Pop = 466,656 | Nearest Stn = 6.00 km | Implied Density = 37,135 pop/km² | Score = 96.68 [drops out of top-10 under assumed density rule; Rank #12 under High EV]
    3. `Site S-03` (21.1703°N, 72.7386°E): Unserved Pop = 466,443 | Nearest Stn = 4.31 km | Implied Density = 37,118 pop/km² | Score = 96.64 [keeps top-10 rank under the assumed density rule; Rank #6 under High EV]
    4. `Site S-04` (21.1477°N, 72.7390°E): Unserved Pop = 465,241 | Nearest Stn = 5.63 km | Implied Density = 37,023 pop/km² | Score = 96.39 [drops out of top-10 under assumed density rule; Rank #13 under High EV]
    5. `Site S-05` (21.1432°N, 72.7390°E): Unserved Pop = 440,359 | Nearest Stn = 5.98 km | Implied Density = 35,043 pop/km² | Score = 91.23 [drops out of top-10 under assumed density rule; Rank #14 under High EV]
    *(Note: Site S-06 [21.1613°N, 72.7388°E, Score 90.86, Implied Density 34,898 pop/km²] keeps top-10 rank under the assumed density rule and jumps from #6 to #2 under High EV due to high local density: 36,745 pop/km²).*
  - **Rajkot Top 5 Candidates**:
    1. `Site R-01` (22.2171°N, 70.8029°E): Unserved Pop = 44,396 | Nearest Stn = 4.71 km | Implied Density = 3,533 pop/km² | Score = 100.00 [keeps top-10 rank under the assumed density rule; Rank #1 under High EV]
    2. `Site R-02` (22.2170°N, 70.7980°E): Unserved Pop = 42,635 | Nearest Stn = 4.70 km | Implied Density = 3,393 pop/km² | Score = 96.03 [keeps top-10 rank under the assumed density rule; Rank #2 under High EV]
    3. `Site R-03` (22.2173°N, 70.8077°E): Unserved Pop = 37,748 | Nearest Stn = 4.75 km | Implied Density = 3,004 pop/km² | Score = 85.02 [keeps top-10 rank under the assumed density rule; Rank #3 under High EV]
    4. `Site R-04` (22.2169°N, 70.7932°E): Unserved Pop = 35,495 | Nearest Stn = 4.69 km | Implied Density = 2,825 pop/km² | Score = 79.95 [keeps top-10 rank under the assumed density rule; Rank #4 under High EV]
    5. `Site R-05` (22.2168°N, 70.7883°E): Unserved Pop = 33,707 | Nearest Stn = 4.74 km | Implied Density = 2,682 pop/km² | Score = 75.92 [keeps top-10 rank under the assumed density rule; Rank #5 under High EV]
- **EV Scenario Effect on 2030 Demand (Module D Part 2)**:
  - *Normalization Rule*: Every scenario multiplier is normalized so that it identically equals 1.0000 in 2026 (divided by 2026 value), ensuring all scenarios start from the same observed Q1 FY27 volume of 3.760 mmscmd.
  - *Source Quote*: NITI Aayog & RMI (2021) "Mobilising Electric Vehicle Financing in India", p. 12: *"The transition to electric vehicles (EVs) in India is targeted to reach 80% sales penetration for two- and three-wheelers, 70% for commercial cars, 40% for buses, and 30% for private cars by 2030."*
  - *Sales vs Fleet Share Conversion*: NITI Aayog targets are **sales-share targets**, not on-road fleet shares. Converted to on-road fleet share ceilings using stock turnover lifetimes [ASSUMPTION]: 8-yr turnover for 3W (55% fleet ceiling), 10-yr turnover for 4W (25% fleet ceiling), 12-yr turnover for buses (28% fleet ceiling).
  - Counterfactual ICE @ 4% CAGR: 2026 = 3.760 mmscmd, 2030 = 4.399 mmscmd [ASSUMPTION].
  - **Low EV Adoption**: Multiplier = 0.9199 (EV fleet share 11.61%) -> Projected Demand = 4.046 mmscmd (**-8.0%** vs counterfactual, +7.6% vs 2026 base).
  - **Medium EV Adoption (Baseline)**: Multiplier = 0.8305 (EV fleet share 23.68%) -> Projected Demand = 3.653 mmscmd (**-16.9%** vs counterfactual, -2.8% vs 2026 base).
  - **High EV Adoption**: Multiplier = 0.6961 (EV fleet share 39.74%) -> Projected Demand = 3.062 mmscmd (**-30.4%** vs counterfactual, -18.6% vs 2026 base).
- **Sanity Validation (5-Seed 20% Station Leave-Out Test)**:
  - Seeds evaluated: `[42, 101, 777, 2023, 9999]`.
  - **Surat**: 0.0% mean recovery (0/5 recovered per seed across all 5 seeds).
  - **Rajkot**: 0.0% mean recovery (0/3 recovered per seed across all 5 seeds).
  - *Honest Diagnosis*: Recovery is 0.0% because conservative $d_{\min} + 1.5$ km ($4.6$ km) exclusion buffers around approximate/pincode-centroid stations blanket the central core even when 20% of reliable stations are removed. Candidate grid cells can only emerge in unconstrained peripheral expansion corridors.
- **Robust Siting Comparison (With vs Without Density Bonus)**:
  - Evaluated under the Urban Density Fleet Resilience Rule [ASSUMPTION]: Dense corridors retain commercial fleet activity (auto-rickshaws, cabs) as peripheral private demand electrifies.
  - **Surat**: 4 sites keep top-10 rank under the assumed density rule across all 3 EV scenarios (Base #6 [21.1613°N, 72.7388°E, pop density 36,745 pop/km²], plus 3 candidates at 21.1658°N, 72.7387°E with pop densities >29,000 pop/km²). Base #6 jumps from #6 to #2 under High EV. Base sites #1–#5 and #7–#10 drop out of the top 10 under the assumed density rule because their surrounding local densities (~13,331–21,570 pop/km²) are lower than inner nodes.
  - **Rajkot**: 8 sites keep top-10 rank under the assumed density rule (#1, #2, #3, #4, #5, #6, #7, #9). Top 5 sites remain rock-solid at ranks #1 through #5 across Base, Low, Medium, and High EV.

## Appendix: Competitor analysis (illustrative: OSM contains very few competitor stations)
- OSM contains only 2 mapped competitor CNG stations within 30 km of Surat and 2 within 30 km of Rajkot (~1% GGCL coverage baseline across Gujarat).
- In Surat, 6/23 (26.1%) of GG stations intersect a 2.0 km competitor buffer, and 20/23 (87.0%) intersect a 6.0 km corridor competitor buffer.
- In Rajkot, 5/14 (35.7%) intersect a 2.0 km competitor buffer, and 13/14 (92.9%) intersect a 6.0 km corridor competitor buffer.
- Due to volunteer mapping incompleteness, competitor proximity is reported purely for illustrative methodological completeness and should not guide commercial capital allocation without full retail census data.
