# Data sources

| File | Source | Date pulled | Licence / terms | Notes |
|---|---|---|---|---|
| raw/osm_cng_stations_gujarat.csv | OpenStreetMap via Overpass API (`https://maps.mail.ru/osm/tools/overpass/api/interpreter`) | 2026-10-14 | ODbL, (c) OpenStreetMap contributors | Volunteer-mapped; coverage vs GGCL's reported station count (~560 stations in Gujarat): **1.07%** (6 Gujarat Gas stations out of 64 total mapped CNG stations in Gujarat) |
| raw/vahan/*.xlsx | VAHAN 4 dashboard (vahan.parivahan.gov.in) | Pending manual download | Open Government Data / Public dashboard | New registrations (flow), not fleet stock; automation blocked by PrimeFaces JSF dynamic overlay controls |
| raw/prices.csv | PPAC (MoPNG), Gujarat Gas Limited / GGL Engage, IOCL archives, Financial Press (TOI, IE, BS, NDTV, Gujarat Samachar) | 2026-10-14 | Public domain & public disclosures | CNG and petrol price changes from 2019 to 2026, reference city: Ahmedabad |
| raw/ggcl_cng_volumes.csv | Gujarat Gas Limited (now Gujarat Energy Limited) quarterly press releases, investor presentations, BSE/NSE filings | 2026-10-14 | Public regulatory disclosures (BSE Scrip: 539336) | Network-level CNG volume, mmscmd from Q1 FY21 through Q1 FY27; quotations documented in `data/raw/ggcl_volume_evidence.md` |

## What is NOT available
Station-level and hourly sales are GGCL internal data and are not public. Where station-level numbers appear in this project they are **estimates** from a documented allocation model.
