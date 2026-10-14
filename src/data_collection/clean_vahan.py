"""
Step 2: Clean VAHAN dashboard exports into a tidy table of CNG registrations.

The VAHAN export layout changes over time, so this script is deliberately
generic and prints what it found. Inspect the output before trusting it.

Typical export: rows = fuel type (or RTO), columns = months (or years).

Run examples:
  pip install pandas openpyxl
  python 02_clean_vahan.py --file vahan_gujarat_2024.xlsx --header-row 3
  python 02_clean_vahan.py --file vahan_gujarat_2024.xlsx --header-row 3 --district-rows
      (use --district-rows when the row label is an RTO/district instead of a fuel type
       and you have already filtered the dashboard to fuel = CNG)

Output: vahan_cng_tidy.csv with columns: label, period, registrations
"""
import argparse
import re
import pandas as pd


def load_raw(path, header_row):
    if path.lower().endswith((".xlsx", ".xls")):
        raw = pd.read_excel(path, header=None)
    else:
        raw = pd.read_csv(path, header=None)
    print("First 8 raw rows (use this to choose --header-row):")
    print(raw.head(8).to_string())
    header = raw.iloc[header_row].astype(str).str.strip().tolist()
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = header
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


def to_number(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def parse_period(label):
    """Turn column headers like 'JAN', 'Jan-2024', '2024', 'FEB 2023' into a date."""
    s = str(label).strip()
    d = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--header-row", type=int, default=0)
    ap.add_argument("--year", type=int, default=None, help="Year to attach when columns are bare month names")
    ap.add_argument("--district-rows", action="store_true", help="Row labels are RTOs/districts (already CNG-only)")
    ap.add_argument("--out", default="vahan_cng_tidy.csv")
    args = ap.parse_args()

    df = load_raw(args.file, args.header_row)
    label_col = df.columns[0]
    df = df.rename(columns={label_col: "label"})
    df["label"] = df["label"].astype(str).str.strip()

    # Drop obvious total / serial-number junk
    df = df[~df["label"].str.lower().isin(["total", "grand total", "nan", "s no", "sl no"])]

    long = df.melt(id_vars="label", var_name="period_raw", value_name="registrations")
    long["registrations"] = to_number(long["registrations"])
    long = long.dropna(subset=["registrations"])

    # Skip a trailing "TOTAL" column
    long = long[~long["period_raw"].str.lower().str.contains("total")]

    if not args.district_rows:
        # Keep only rows whose fuel label mentions CNG (CNG ONLY, PETROL/CNG, etc.)
        long = long[long["label"].str.contains("cng", case=False, regex=True)]

    def make_period(x):
        s = str(x)
        if args.year and re.fullmatch(r"[A-Za-z]{3,9}", s):
            s = f"{s} {args.year}"
        return parse_period(s)

    long["period"] = long["period_raw"].apply(make_period)
    long = long.dropna(subset=["period"])
    long = long[["label", "period", "registrations"]].sort_values(["label", "period"])

    long.to_csv(args.out, index=False)
    print(f"\nSaved {len(long)} rows -> {args.out}")
    print(long.head(12).to_string(index=False))
    print(
        "\nREMINDER: these are NEW registrations per period (a flow), not the total fleet on the road. "
        "Build a cumulative sum from your earliest year if you want a fleet-size proxy."
    )


if __name__ == "__main__":
    main()
