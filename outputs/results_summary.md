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
- Top 5 candidate sites: _list_
- EV scenario effect on 2030 demand (low / medium / high): _% change_

## Appendix: Competitor analysis (illustrative: OSM contains very few competitor stations)
- OSM contains only 2 mapped competitor CNG stations within 30 km of Surat and 2 within 30 km of Rajkot (~1% GGCL coverage baseline across Gujarat).
- In Surat, 6/23 (26.1%) of GG stations intersect a 2.0 km competitor buffer, and 20/23 (87.0%) intersect a 6.0 km corridor competitor buffer.
- In Rajkot, 5/14 (35.7%) intersect a 2.0 km competitor buffer, and 13/14 (92.9%) intersect a 6.0 km corridor competitor buffer.
- Due to volunteer mapping incompleteness, competitor proximity is reported purely for illustrative methodological completeness and should not guide commercial capital allocation without full retail census data.
