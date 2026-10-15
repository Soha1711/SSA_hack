"""
Module: build_master_table.py
Part 1 of Task 2: Build the quarterly master table for Gujarat Gas CNG demand forecasting.

Constructs data/processed/quarterly_master.csv combining:
1. GGCL quarterly CNG sales volume (mmscmd) from data/raw/ggcl_cng_volumes.csv
2. VAHAN monthly CNG-capable registrations from data/processed/vahan_cng_tidy.csv
3. Retail fuel prices (CNG and Petrol in Ahmedabad) from data/raw/prices.csv
"""

from pathlib import Path
import pandas as pd
import numpy as np

from src.utils import ROOT, RAW, PROCESSED


def generate_quarter_grid():
    """
    Generate Indian fiscal quarters from Q4 FY19 (Jan-Mar 2019) to Q2 FY27 (Jul-Sep 2026).
    Indian fiscal year:
      Q1: Apr 1 - Jun 30
      Q2: Jul 1 - Sep 30
      Q3: Oct 1 - Dec 31
      Q4: Jan 1 - Mar 31
    """
    records = []
    # 2019 Q4 FY19
    records.append(("Q4 FY19", "2019-01-01", "2019-03-31"))
    
    # FY20 to FY26
    for fy in range(20, 27):
        cal_start = 2000 + fy - 1
        cal_end = 2000 + fy
        records.append((f"Q1 FY{fy}", f"{cal_start}-04-01", f"{cal_start}-06-30"))
        records.append((f"Q2 FY{fy}", f"{cal_start}-07-01", f"{cal_start}-09-30"))
        records.append((f"Q3 FY{fy}", f"{cal_start}-10-01", f"{cal_start}-12-31"))
        # Leap year check for Feb in Q4
        records.append((f"Q4 FY{fy}", f"{cal_end}-01-01", f"{cal_end}-03-31"))
        
    # FY27: Q1 and Q2
    records.append(("Q1 FY27", "2026-04-01", "2026-06-30"))
    records.append(("Q2 FY27", "2026-07-01", "2026-09-30"))
    
    df = pd.DataFrame(records, columns=["quarter", "quarter_start", "quarter_end"])
    df["quarter_start"] = pd.to_datetime(df["quarter_start"])
    df["quarter_end"] = pd.to_datetime(df["quarter_end"])
    df["days_in_quarter"] = (df["quarter_end"] - df["quarter_start"]).dt.days + 1
    return df


def compute_day_weighted_prices(quarter_df, prices_path):
    """
    Compute day-weighted average CNG and Petrol prices per quarter.
    A price stays in force until the next change; forward-fill within the price series only.
    Quarters before any price event exists are left blank (NaN).
    """
    prices = pd.read_csv(prices_path)
    prices["date"] = pd.to_datetime(prices["date"])
    
    min_date = quarter_df["quarter_start"].min()
    max_date = quarter_df["quarter_end"].max()
    daily_grid = pd.DataFrame({"date": pd.date_range(min_date, max_date, freq="D")})
    
    # CNG prices
    cng_series = prices.dropna(subset=["cng_price_inr_per_kg"])[["date", "cng_price_inr_per_kg"]].sort_values("date")
    daily_grid = daily_grid.merge(cng_series, on="date", how="left")
    daily_grid["cng_price_ffill"] = daily_grid["cng_price_inr_per_kg"].ffill()
    
    # Petrol prices
    petrol_series = prices.dropna(subset=["petrol_price_inr_per_litre"])[["date", "petrol_price_inr_per_litre"]].sort_values("date")
    daily_grid = daily_grid.merge(petrol_series, on="date", how="left")
    daily_grid["petrol_price_ffill"] = daily_grid["petrol_price_inr_per_litre"].ffill()
    
    cng_avgs = []
    petrol_avgs = []
    
    for _, row in quarter_df.iterrows():
        mask = (daily_grid["date"] >= row["quarter_start"]) & (daily_grid["date"] <= row["quarter_end"])
        sub = daily_grid[mask]
        
        # CNG average
        cng_valid = sub["cng_price_ffill"].dropna()
        if cng_valid.empty:
            cng_avgs.append(np.nan)
        else:
            cng_avgs.append(round(cng_valid.mean(), 2))
            
        # Petrol average
        petrol_valid = sub["petrol_price_ffill"].dropna()
        if petrol_valid.empty:
            petrol_avgs.append(np.nan)
        else:
            petrol_avgs.append(round(petrol_valid.mean(), 2))
            
    quarter_df["cng_price_avg"] = cng_avgs
    quarter_df["petrol_price_avg"] = petrol_avgs
    quarter_df["price_ratio"] = (quarter_df["petrol_price_avg"] / quarter_df["cng_price_avg"]).round(4)
    return quarter_df


def aggregate_vahan_registrations(quarter_df, vahan_path):
    """
    Sum new registrations across ALL CNG-capable fuel labels in each quarter.
    Compute cng_fleet_proxy as cumulative sum of registrations from Jan 2019.
    """
    vahan = pd.read_csv(vahan_path)
    vahan["period"] = pd.to_datetime(vahan["period"])
    
    def match_quarter(dt):
        for _, row in quarter_df.iterrows():
            if row["quarter_start"] <= dt <= row["quarter_end"]:
                return row["quarter"]
        return None
        
    vahan["quarter"] = vahan["period"].apply(match_quarter)
    q_sums = vahan.groupby("quarter")["registrations"].sum().reset_index()
    q_sums.rename(columns={"registrations": "cng_registrations_q"}, inplace=True)
    
    quarter_df = quarter_df.merge(q_sums, on="quarter", how="left")
    quarter_df["cng_registrations_q"] = quarter_df["cng_registrations_q"].fillna(0).astype(int)
    quarter_df["cng_fleet_proxy"] = quarter_df["cng_registrations_q"].cumsum()
    return quarter_df


def merge_volumes(quarter_df, volumes_path):
    """
    Merge official quarterly CNG volume from ggcl_cng_volumes.csv.
    Unreleased/missing values are left as blank (NaN).
    """
    vols = pd.read_csv(volumes_path)
    vol_map = dict(zip(vols["quarter"], vols["cng_volume_mmscmd"]))
    quarter_df["cng_volume_mmscmd"] = quarter_df["quarter"].map(vol_map)
    return quarter_df


def build_master_table():
    q_df = generate_quarter_grid()
    q_df = merge_volumes(q_df, RAW / "ggcl_cng_volumes.csv")
    q_df = aggregate_vahan_registrations(q_df, PROCESSED / "vahan_cng_tidy.csv")
    q_df = compute_day_weighted_prices(q_df, RAW / "prices.csv")
    
    # Covid flag: 1 for Q1 FY21 and Q2 FY21, else 0
    q_df["covid_flag"] = q_df["quarter"].apply(lambda q: 1 if q in ["Q1 FY21", "Q2 FY21"] else 0)
    
    # Format dates as YYYY-MM-DD strings
    q_df["quarter_start"] = q_df["quarter_start"].dt.strftime("%Y-%m-%d")
    q_df["quarter_end"] = q_df["quarter_end"].dt.strftime("%Y-%m-%d")
    
    # Reorder columns as requested
    cols = [
        "quarter",
        "quarter_start",
        "quarter_end",
        "cng_volume_mmscmd",
        "cng_registrations_q",
        "cng_fleet_proxy",
        "cng_price_avg",
        "petrol_price_avg",
        "price_ratio",
        "covid_flag",
        "days_in_quarter",
    ]
    master = q_df[cols]
    
    out_path = PROCESSED / "quarterly_master.csv"
    master.to_csv(out_path, index=False)
    print(f"Saved {len(master)} rows to {out_path}")
    return master


def write_notes():
    notes_content = """# Master Table Transformations and Assumptions Notes

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
"""
    notes_path = PROCESSED / "MASTER_TABLE_NOTES.md"
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write(notes_content)
    print(f"Wrote notes to {notes_path}")


def main():
    build_master_table()
    write_notes()


if __name__ == "__main__":
    main()
