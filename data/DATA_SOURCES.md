# Data sources

| File | Source | Date pulled | Licence / terms | Notes |
|---|---|---|---|---|
| raw/osm_cng_stations_gujarat.csv | OpenStreetMap via Overpass API (`https://maps.mail.ru/osm/tools/overpass/api/interpreter`) | 2026-10-14 | ODbL, (c) OpenStreetMap contributors | Volunteer-mapped; coverage vs GGCL's reported station count (~560 stations in Gujarat): **1.07%** (6 Gujarat Gas stations out of 64 total mapped CNG stations in Gujarat) |
| raw/vahan/reportTable_*.xlsx & processed/vahan_cng_tidy.csv | MoRTH VAHAN 4 dashboard (`vahan.parivahan.gov.in/vahan4dashboard/vahan/vahan/view/reportview.xhtml`) | 2026-10-14 | Open Government Data / Public dashboard | Monthly new vehicle registrations (flow) for Gujarat state, 2019 to 2026 (Jan 2019 - Sep 2026, 453 tidy rows; partial month of October 2026 removed to ensure full calendar months). Filtered to CNG-capable powertrains (CNG ONLY, PETROL/CNG, hybrid/flex CNG variants). |
| raw/prices.csv | PPAC (MoPNG), Gujarat Gas Limited / GGL Engage, IOCL archives, Financial Press (TOI, IE, BS, NDTV, Gujarat Samachar) | 2026-10-14 | Public domain & public disclosures | CNG and petrol price changes from 2019 to 2026, reference city: Ahmedabad |
| raw/ggcl_cng_volumes.csv | Gujarat Gas Limited (now Gujarat Energy Limited) quarterly press releases, investor presentations, BSE/NSE filings | 2026-10-14 | Public regulatory disclosures (BSE Scrip: 539336) | Network-level CNG volume, mmscmd from Q1 FY21 through Q1 FY27; quotations documented in `data/raw/ggcl_volume_evidence.md` |
| raw/cng_stations_by_ga.csv | PNGRB Progress Reports & MoPNG Parliamentary Q&A (Lok Sabha / Rajya Sabha) | 2026-10-15 | Public parliamentary records & regulatory disclosures | Official Geographical Area (GA)-wise CNG station counts for Gujarat as of 31.03.2019, 31.10.2022, and 31.05.2024. |
| raw/station_addresses_<city>.csv | Gujarat Gas Limited official CNG station directory (`https://www.gujaratgas.com/cng/cng-stations/`) | 2026-10-15 | Public corporate station directory (General terms & disclaimer) | Verified operational station names, street addresses, talukas, districts, and pin codes for Ahmedabad (31), Surat (78), and Vadodara (5). Not geocoded. |

## What is NOT available
Station-level and hourly sales are GGCL internal data and are not public. Where station-level numbers appear in this project they are **estimates** from a documented allocation model.
