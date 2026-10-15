# Master Table Transformations and Assumptions Notes

**Output File**: `data/processed/quarterly_master.csv`  
**Generated On**: October 15, 2026  
**Scope**: Indian Fiscal Quarters from Q4 FY19 (Jan–Mar 2019) to Q2 FY27 (Jul–Sep 2026) — 31 quarters total.

---

## 1. Column Specifications & Derivations

| Column | Description | Source / Derivation | Missing Value Handling |
|---|---|---|---|
| `quarter` | Fiscal Quarter label (e.g. `Q1 FY24`) | Standard Indian Fiscal Calendar (`Q1`: Apr–Jun, `Q2`: Jul–Sep, `Q3`: Oct–Dec, `Q4`: Jan–Mar). | None (31 discrete periods). |
| `quarter_start` | First calendar day of quarter (`YYYY-MM-DD`) | Calendar arithmetic. | Complete. |
| `quarter_end` | Last calendar day of quarter (`YYYY-MM-DD`) | Calendar arithmetic. | Complete. |
| `cng_volume_mmscmd` | Network-level quarterly CNG sales volume | Primary disclosures in `data/raw/ggcl_cng_volumes.csv` (Q1 FY21 to Q1 FY27). | Blank (`NaN`) for unreleased Q2 FY27 and unobserved pre-FY21 quarters. Zero interpolation. |
| `cng_registrations_q` | New CNG registrations in the quarter | Sum of monthly flow registrations across all CNG-capable powertrains in `data/processed/vahan_cng_tidy.csv`. | Complete for all 31 quarters (93 months). |
| `cng_fleet_proxy` | Cumulative CNG vehicle stock proxy | Running cumulative sum of `cng_registrations_q` starting Jan 1, 2019. | Complete. Explicitly labelled as proxy (no scrappage deducted, initial pre-2019 base assumed 0). |
| `cng_price_avg` | Day-weighted average CNG retail price (₹/kg) | Daily date grid forward-filling price change events from `data/raw/prices.csv`. | Blank (`NaN`) for Q4 FY19 and Q1 FY20 prior to first recorded CNG tariff event (2019-07-04). |
| `petrol_price_avg` | Day-weighted average Petrol retail price (₹/L) | Daily date grid forward-filling price change events from `data/raw/prices.csv`. | Complete (initial event recorded on 2019-01-01 at ₹65.91/L). |
| `price_ratio` | Economic competitiveness ratio | `petrol_price_avg / cng_price_avg`. Higher ratio indicates stronger financial incentive to drive CNG. | Blank (`NaN`) for quarters where `cng_price_avg` is unobserved. |
| `covid_flag` | Lockdown indicator dummy | Indicator variable: `1` for Q1 FY21 (Apr–Jun 2020 national lockdown) and Q2 FY21 (Jul–Sep 2020 staged unlock), `0` otherwise. | Complete. |
| `days_in_quarter` | Total days in quarter | `(quarter_end - quarter_start) + 1` (90, 91, or 92 days, accurately capturing leap years 2020 and 2024). | Complete. |

---

## 2. Key Data Integrity Rules & Non-Estimations

1. **No Backfilled Prices**: Prior to July 4, 2019, Gujarat Gas retail CNG tariff revisions are not documented in `prices.csv`. In strict compliance with Rule 1 ("never invent or interpolate observed values"), `cng_price_avg` and `price_ratio` are left blank (`NaN`) rather than guessed from national averages.
2. **Persistent Forward-Filling**: Retail fuel tariffs in India remain legally in force until a formal price revision notice is published by OMCs or CGD operators. Forward-filling within the price series is therefore the only empirically grounded representation of daily tariffs.
3. **Sparse Station Counts Excluded**: Per prompt instruction, station counts from `cng_stations_by_ga.csv` and `ggcl_cng_volumes.csv` are sparse and are not used as modeling features.
4. **Target Holdout**: `Q2 FY27` volume remains blank as the financial results are scheduled for release at the Board Meeting on November 5, 2026.
