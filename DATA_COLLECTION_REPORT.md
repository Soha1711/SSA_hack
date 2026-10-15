# Step 1: Real Data Collection and Cleaning Report
**Project**: CNG Demand Forecasting for Gujarat Gas Limited (Hackathon PS000002)  
**Date**: October 14, 2026  
**Scope**: Step 1 — Real Data Collection, Automated Cleaning, and Source Verification  

---

## 1. Executive Summary

This report documents the completion of **Step 1 (Real Data Collection and Cleaning)** for the Gujarat Gas CNG Demand Forecasting project. In accordance with the project's non-negotiable data integrity guidelines:
- **Zero Synthetic Data**: No numbers were invented, estimated, interpolated, or backfilled with "plausible" defaults.
- **Traceable Provenance**: Every row records its primary source URL, regulatory filing, or official government dashboard.
- **Clean Separation**: Raw downloads remain untouched in `data/raw/`, with cleaned tidy tables written to `data/processed/`.
- **Local Version Control**: Discrete local Git commits were made after every milestone task without pushing.

All four core empirical datasets—OSM station locations, quarterly network volumes, historical retail fuel prices, and VAHAN monthly vehicle registrations—are collected, cleaned, cross-validated, and documented.

---

## 2. File Inventory & Row Counts

| File Path | Description | Records / Rows | Date Coverage | Source / Authority |
|---|---|:---:|:---:|---|
| [`data/raw/osm_cng_stations_gujarat.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/osm_cng_stations_gujarat.csv) | CNG fueling stations in Gujarat | 64 stations | Snapshot 2026-10-14 | OpenStreetMap via Overpass API |
| [`data/raw/station_addresses_ahmedabad.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_ahmedabad.csv) | Gujarat Gas operational CNG stations (Ahmedabad) | 31 stations | Active Directory 2026 | Gujarat Gas official station directory (`gujaratgas.com`) |
| [`data/raw/station_addresses_surat.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_surat.csv) | Gujarat Gas operational CNG stations (Surat) | 78 stations | Active Directory 2026 | Gujarat Gas official station directory (`gujaratgas.com`) |
| [`data/raw/station_addresses_vadodara.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_vadodara.csv) | Gujarat Gas operational CNG stations (Vadodara) | 5 stations | Active Directory 2026 | Gujarat Gas official station directory (`gujaratgas.com`) |
| [`data/raw/cng_stations_by_ga.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/cng_stations_by_ga.csv) | Official Geographical Area (GA)-wise station counts | 37 rows | 2019-03-31, 2022-10-31, 2024-05-31 | PNGRB Progress Reports & Parliamentary Q&A (Sansad) |
| [`data/raw/ggcl_cng_volumes.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_cng_volumes.csv) | GGCL network-level quarterly CNG sales volume | 26 quarters | Q1 FY21 to Q2 FY27 | GGCL investor presentations & BSE filings (Scrip: 539336) |
| [`data/raw/ggcl_volume_evidence.md`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_volume_evidence.md) | Exact quotations & filing URLs for volumes & stations | 26 sections | FY21 to FY27 | Official BSE/NSE company disclosures |
| [`data/raw/prices.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/prices.csv) | CNG and Petrol price change events (Ahmedabad) | 38 events | 2019-01-01 to 2026-08-16 | PPAC (MoPNG), Gujarat Gas tariff notices, IOCL archives |
| [`data/raw/vahan/reportTable_2019.xlsx`](file:///f:/SSA_hack/cng-demand-planner/data/raw/vahan/reportTable_2019.xlsx) to `reportTable_2026.xlsx` | 8 raw annual VAHAN exports for Gujarat | 8 workbooks (16–23 rows each) | Jan 2019 to Oct 2026 | MoRTH VAHAN 4 Dashboard |
| [`data/processed/vahan_cng_tidy.csv`](file:///f:/SSA_hack/cng-demand-planner/data/processed/vahan_cng_tidy.csv) | Cleaned, melted monthly CNG vehicle registrations | 453 monthly rows | 2019-01-01 to 2026-09-01 | Derived from VAHAN exports (Oct 2026 partial month pruned) |
| [`data/DATA_SOURCES.md`](file:///f:/SSA_hack/cng-demand-planner/data/DATA_SOURCES.md) | Canonical documentation of sources & terms | 6 datasets | Ongoing | Open Data / Regulatory Disclosures |

---

## 3. Detailed Task Review

### Task 1 — OpenStreetMap CNG Stations
- **Script**: [`src/data_collection/fetch_osm_stations.py`](file:///f:/SSA_hack/cng-demand-planner/src/data_collection/fetch_osm_stations.py)
- **Modifications**: Added custom `User-Agent: CNGDemandPlanner/1.0` header, responsive fallback Overpass mirror (`https://maps.mail.ru/osm/tools/overpass/api/interpreter`), and geographic bounding box fallback `(20.0, 68.0, 24.8, 74.6)`.
- **Output Metrics**:
  - Raw stations fetched: 64
  - Exact coordinate duplicates: 0
  - Spatial near-duplicates (< 50 meters): 0
  - Out-of-bounds stations: 0
- **Brand / Operator Breakdown**:
  - Unknown / Unbranded: 40
  - Indian Oil (IOCL): 7
  - Bharat Petroleum (BPCL): 6
  - Gujarat Gas Limited (GGCL): 6 (explicitly branded)
  - Adani Total Gas: 2
  - Sabarmati Gas: 4 (including variants)
  - Hindustan Petroleum (HPCL): 3
  - Bharat Gas Resources Limited: 1
  - Nayara Energy: 1
- **Coverage Assessment**: OSM contains 6 explicitly tagged Gujarat Gas stations against ~560 stations reported by GGCL across Gujarat (~825+ total network). Mapped coverage is **1.07%**. This proves OSM is insufficient for network-wide retail demand modeling on its own and requires CGD administrative boundary allocation or synthetic station expansion.

### Task 2 — Gujarat Gas Quarterly CNG Volumes
- **File**: [`data/raw/ggcl_cng_volumes.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_cng_volumes.csv)
- **Evidence File**: [`data/raw/ggcl_volume_evidence.md`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_volume_evidence.md)
- **Coverage**: 26 quarters (Q1 FY21 through Q2 FY27).
- **Integrity Check**: The three pre-existing verified anchor rows in the template were preserved without conflict:
  - `Q1 FY24`: **2.61 mmscmd**
  - `Q3 FY24`: **2.78 mmscmd** (Station count: 562)
  - `Q1 FY25`: **2.98 mmscmd**
- **Trend Highlight**: CNG sales expanded from **1.38 mmscmd in Q1 FY21** (COVID-19 lockdown trough) to **3.01 mmscmd in Q4 FY25**, maintaining steady volume near **2.88 mmscmd in Q1 FY27**.
- **Missing Value**: `Q2 FY27` volume is left completely empty (`NaN`) as results will be released at the Board Meeting on November 5, 2026.

### Task 3 — Historical Fuel Prices (Ahmedabad Reference City)
- **File**: [`data/raw/prices.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/prices.csv)
- **Scope**: 38 discrete price change events from January 2019 to August 2026.
  - 21 Gujarat Gas CNG retail price changes (from ₹55.55/kg in July 2019 to peak of ₹78.25/kg in 2022–2023, and ₹78.25/kg in August 2026).
  - 17 Petrol retail selling price changes (from ₹65.91/L in Jan 2019 to ₹94.42/L in 2024–2026).
- **Sources**: Petroleum Planning & Analysis Cell (PPAC, Ministry of Petroleum and Natural Gas), Gujarat Gas tariff notices / GGL Engage, IOCL retail price archives, and certified financial press reports (Times of India, Indian Express, Business Standard, NDTV, Gujarat Samachar).

### Task 4 — VAHAN Vehicle Registrations (Gujarat State)
- **Raw Files**: 8 workbooks in [`data/raw/vahan/`](file:///f:/SSA_hack/cng-demand-planner/data/raw/vahan/) (`reportTable_2019.xlsx` through `reportTable_2026.xlsx`).
- **Script**: [`src/data_collection/clean_vahan.py`](file:///f:/SSA_hack/cng-demand-planner/src/data_collection/clean_vahan.py)
- **Output**: [`data/processed/vahan_cng_tidy.csv`](file:///f:/SSA_hack/cng-demand-planner/data/processed/vahan_cng_tidy.csv) (458 monthly rows).

#### Bug Diagnosis & Fix:
- **Error**: `AttributeError: 'DataFrame' object has no attribute 'str'` when passing `--header-row 3`.
- **Cause**: In the VAHAN export, Row 3 has `NaN` in Column 0 (`S No`) and Column 1 (`Fuel`). When headers were assigned, columns 0 and 1 were both named `'nan'`. Renaming `'nan'` to `'label'` caused `df['label']` to be a 2-column DataFrame, which lacks the string accessor `.str`.
- **Solution**: Updated `load_raw` to inspect Column 0 for serial numbers (`1, 2, 3...`) and assign Column 1 as the true category label, dropping the serial number column and ensuring all column headers are unique.
- **Batch Processing**: Extended `clean_vahan.py` to accept `--dir` or wildcards, parse each year from row 0 / filename, and output a unified tidy dataset.

#### Spot-Check Verification Table:

| Spot Check # | Raw Excel File | Cell Coordinate | Fuel Category | Target Month | Raw Cell Value | Parsed Value in Tidy CSV | Verification |
|:---:|---|:---:|---|:---:|:---:|:---:|:---:|
| **1** | `reportTable_2024.xlsx` | `L5` (Row 5, Col 12) | `CNG ONLY` | 2024-10-01 (Oct 2024) | `"14,514"` | **14514** | Exact Match |
| **2** | `reportTable_2024.xlsx` | `C14` (Row 14, Col 3) | `PETROL/CNG` | 2024-01-01 (Jan 2024) | `"12,298"` | **12298** | Exact Match |
| **3** | `reportTable_2019.xlsx` | `G5` (Row 5, Col 7) | `CNG ONLY` | 2019-05-01 (May 2019) | `"42"` | **42** | Exact Match |
| **4** | `reportTable_2026.xlsx` | `C5` (Row 5, Col 3) | `CNG ONLY` | 2026-01-01 (Jan 2026) | `"9,972"` | **9972** | Exact Match |

---

## 4. Missing Data & Unreleased Values (Rule 1 Compliance)

| Variable | Missing Segment | Reason for Absence | Where It Exists / When Expected | Handling in Pipeline |
|---|---|---|---|---|
| `cng_volume_mmscmd` | **Q2 FY27** | Period just ended (September 30, 2026); Board Meeting scheduled for November 5, 2026. | Gujarat Gas Limited Q2 FY27 Earnings Release (BSE/NSE). | Kept as blank cell (`NaN`). Downstream forecasting must treat this as target holdout or predict it. |
| `cng_stations` | **Unstated Quarters** | GGCL began disclosing exact Gujarat operational station counts in specific quarterly presentations (e.g. Q4 FY21: 559, Q4 FY22: 561, Q1 FY24: 559, Q2 FY24: 554, Q3 FY24: 562, Q4 FY24: 565, Q1 FY25: 554). Later quarters (FY26–FY27) only state total company-wide network (839–844 stations across India) without isolated Gujarat breakdown. | Gujarat Gas Annual Reports & Investor Presentations. | Blank cells in `ggcl_cng_volumes.csv` for quarters lacking explicit Gujarat-specific station disclosure. |
| VAHAN Registrations | **Oct, Nov & Dec 2026** | Partial month of October 2026 was removed; Nov/Dec future dates have not elapsed. | MoRTH VAHAN Dashboard. | Dataset strictly covers full completed calendar months from `2019-01-01` to `2026-09-01`. |
| Station-Level Daily Sales | **All stations** | Proprietary commercial data; not published by GGCL or PNGRB. | Internal GGCL SAP / SCADA systems. | Cannot be collected from public web. Downstream models must estimate via spatial and vehicle-stock allocation. |

---

## 5. Potential Conflicts, Nuances & Data Quality Observations

1. **Station Count Mismatch (OSM vs. Annual Report)**:
   - OSM identifies 64 CNG stations across all CGD entities in Gujarat, with only 6 tagged as Gujarat Gas.
   - GGCL's regulatory presentations state **>560 operational CNG stations** in Gujarat (>825 total across all GAs).
   - *Impact*: Models cannot rely on OSM alone to establish station density without synthetic expansion or RTO-level clustering.
2. **VAHAN Flow vs. Stock**:
   - VAHAN data reports *new vehicle registrations per month* (flow), not active fleet on the road (stock).
   - Because vehicles remain operational for 10–15 years, a cumulative sum (net of scrappage) should be used as a proxy for vehicle fleet size.
3. **Powertrain Categorization Shift**:
   - Prior to 2022, registrations were classified simply as `CNG ONLY` and `PETROL/CNG`.
   - Post-2023, ethanol mandates introduced `PETROL(E20)/CNG`, `PETROL(E20)/HYBRID/CNG`, and `PETROL/HYBRID/CNG`. All 6 CNG-capable categories are retained in the tidy dataset.
4. **Corporate Restructuring**:
   - In August–September 2024, the Gujarat Government announced the merger of Gujarat State Petroleum Corporation (GSPC), GSPC Energy, and Gujarat Gas Limited into **Gujarat Energy Limited**. Regulatory filings remain filed under BSE Scrip `539336`.
5. **CGD Administrative Boundaries (Ahmedabad, Surat, Vadodara)**:
   - **Ahmedabad**: Ahmedabad City and Daskroi GA was awarded to Adani Total Gas Limited (ATGL), whereas Gujarat Gas operates in Ahmedabad District / Rural (31 operational stations).
   - **Surat**: Surat, Bharuch, and Ankleshwar GA is Gujarat Gas's flagship territory (78 operational stations in Surat district).
   - **Vadodara**: Vadodara City GA is operated by Vadodara Gas Limited (VGL - JV of GAIL Gas & VMSS), while Gujarat Gas operates 5 stations in rural/transit highways of Vadodara district (Karjan, Dabhoi, Waghodia).

---

## 6. Manual Verification Checklist for the Team

Before training downstream demand forecasting models, the team should execute these manual checks:
- [ ] **Cross-verify Q1 FY27 volume**: Re-read Slide 9 of the Q1 FY27 presentation to confirm the 2.88 mmscmd CNG figure after final audit adjustments.
- [ ] **Update Q2 FY27 upon release**: On November 5, 2026, check BSE Announcements (`BSE: 539336`) for the Q2 FY27 financial results and enter the volume figure.
- [ ] **Check Ahmedabad vs. Surat/Rajkot Gas Tariff Parity**: GGCL occasionally applies district-level differential VAT or transport charges (~₹0.50–₹1.50/kg). Verify whether Ahmedabad CNG prices serve as an adequate proxy for south Gujarat GAs.
- [ ] **Calculate Cumulative Fleet Stock**: Run a cumulative sum notebook over `data/processed/vahan_cng_tidy.csv` applying a 15-year vehicle survival curve to derive an accurate active CNG fleet covariate.

---

## 7. Step 1 Follow-Up & Refinements (October 15, 2026)

### 1. VAHAN Partial Month Removal
- **File Modified**: [`data/processed/vahan_cng_tidy.csv`](file:///f:/SSA_hack/cng-demand-planner/data/processed/vahan_cng_tidy.csv)
- **Changes**: Removed all 5 records with period `2026-10-01` (`CNG ONLY`: 4132, `PETROL(E20)/CNG`: 5336, `PETROL/CNG`: 804, hybrids: 0).
- **Result**: Row count pruned from 458 to 453. Data now represents exactly 93 completed calendar months (`2019-01-01` through `2026-09-01`).
- **Documentation**: Updated [`data/DATA_SOURCES.md`](file:///f:/SSA_hack/cng-demand-planner/data/DATA_SOURCES.md).

### 2. VAHAN RTO Automation Assessment & Manual Download Instructions
- **Automation Status**: Direct headless scraping was blocked due to PrimeFaces JSF dynamic ViewState handling, bot detection headers, and browser popup blocking on `.gov.in` download requests.
- **Data Quality Observation**: The default table on VAHAN when selecting Y-Axis = `Rto` without opening the filter drawer displays **all fuel types** (~17,651 monthly registrations in Surat in Jan 2019). To extract true CNG registrations, the filter drawer must be opened.
- **Manual Download Instructions for the Team**:
  1. Open `https://vahan.parivahan.gov.in/vahan4dashboard/vahan/vahan/view/reportview.xhtml`.
  2. Select **State**: `Gujarat(38)`.
  3. Set **Y-Axis**: `Rto`, **X-Axis**: `Month Wise`, **Year Type**: `Calendar Year`.
  4. Click the vertical red tab on the far left edge: **"Click Here to Filter"**.
  5. Under **Fuel**, select **`CNG ONLY`** (and separately **`PETROL/CNG`** if multi-select is not supported).
  6. Click **Refresh**.
  7. Allow pop-ups/downloads for `vahan.parivahan.gov.in` in your browser settings (URL bar lock icon -> Site settings -> Pop-ups -> Allow).
  8. Click the green Excel/CSV icon above the table to download each calendar year (`2019` to `2026`). Save into `data/raw/vahan/`.

### 3. Geographical-Area-Wise CNG Stations (`cng_stations_by_ga.csv`)
- **File Created**: [`data/raw/cng_stations_by_ga.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/cng_stations_by_ga.csv)
- **Columns**: `date, geographical_area, district, cng_stations, source_url, page`
- **Official Milestones Captured**:
  - **31.03.2019**: PNGRB CGD Progress Report (Surat/Bharuch: 118, Ahmedabad City: 72, Vadodara City: 32, Rajkot: 48, etc.).
  - **31.10.2022**: MoPNG Parliamentary Reply (Lok Sabha / Rajya Sabha AU629 Annexure-I) across 23 authorized GAs.
  - **31.05.2024**: MoPNG Parliamentary Reply (Rajya Sabha AU2521 Annexure-I) reporting 1,108 cumulative operational CNG stations across Gujarat.
- **Rule 1 Compliance**: No missing areas were interpolated or estimated.

### 4. Gujarat Gas Quarterly Station Disclosures
- **Files Modified**: [`data/raw/ggcl_cng_volumes.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_cng_volumes.csv) & [`data/raw/ggcl_volume_evidence.md`](file:///f:/SSA_hack/cng-demand-planner/data/raw/ggcl_volume_evidence.md)
- **Filled Quarters**:
  - `Q1 FY24 (2023-06-30)`: **559** stations in Gujarat.
  - `Q2 FY24 (2023-09-30)`: **554** stations in Gujarat (out of 806 total network).
  - `Q1 FY25 (2024-06-30)`: **554** stations in Gujarat (out of 811 total network).
- **Exact Quotes**: Cited in `ggcl_volume_evidence.md` with BSE filing links.

### 5. Station Address Directories (Ahmedabad, Surat, Vadodara)
- **Files Created**:
  - [`data/raw/station_addresses_ahmedabad.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_ahmedabad.csv): **31 stations**
  - [`data/raw/station_addresses_surat.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_surat.csv): **78 stations**
  - [`data/raw/station_addresses_vadodara.csv`](file:///f:/SSA_hack/cng-demand-planner/data/raw/station_addresses_vadodara.csv): **5 stations**
- **Source**: Gujarat Gas Official Directory (`https://www.gujaratgas.com/cng/cng-stations/`).
- **Terms Verified**: Public informational directory permitted under general corporate terms and disclaimer (`https://www.gujaratgas.com/disclaimer/`).
- **Fields Stored**: `station_name, address, district, pincode, station_type, source_url`. No geocoding performed.

---

## 8. Git Commit Log

```text
d5f20e5 Step 1 Follow-up: Add official GA-wise station counts and Gujarat Gas city station address directories
754a638 Step 1 Follow-up: Fill cng_stations_gujarat for stated quarters and cite filing evidence
4fb011c Step 1 Follow-up: Remove partial October 2026 month from VAHAN tidy dataset and document in DATA_SOURCES.md
773de52 Add Step 1 Data Collection Report summarizing datasets, spot checks, and verification checklist
787a233 Task 4: Clean and combine VAHAN Gujarat CNG vehicle registrations 2019-2026 into tidy table
64a93ad Task 5: Update DATA_SOURCES.md with pull dates, URLs, licences, and OSM coverage %
dc03493 Task 3: Populate historical fuel prices (CNG and petrol) for Ahmedabad reference city from 2019 to 2026
a75b479 Task 2: Collect real GGCL quarterly CNG volumes from Q1 FY21 with evidence quotations
bda5918 Task 1: Fetch OSM CNG stations in Gujarat and add mirror fallback
```
