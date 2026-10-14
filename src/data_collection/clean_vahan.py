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
    print(f"\nFirst 8 raw rows of {path} (use this to choose --header-row):")
    print(raw.head(8).to_string())

    # Detect if col 0 is serial numbers and col 1 is label (e.g. VAHAN format)
    col0_sample = raw.iloc[header_row + 1 : header_row + 10, 0].dropna().astype(str).str.strip()
    is_col0_sno = len(col0_sample) > 0 and col0_sample.str.isdigit().all()

    header = raw.iloc[header_row].tolist()
    cleaned_header = []
    for idx, col in enumerate(header):
        val = str(col).strip() if pd.notna(col) else ""
        if val in ["", "nan", "None"]:
            if idx == 0 and is_col0_sno:
                val = "s_no"
            elif (idx == 1 and is_col0_sno) or idx == 0:
                val = "label"
            elif idx == len(header) - 1:
                val = "TOTAL"
            else:
                val = f"col_{idx}"
        cleaned_header.append(val)

    df = raw.iloc[header_row + 1 :].copy()
    df.columns = cleaned_header
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if is_col0_sno and "s_no" in df.columns:
        df = df.drop(columns=["s_no"])

    # Infer year if available from title row or filename
    m = re.search(r"\((\d{4})\)", str(raw.iloc[0, 0]))
    if not m:
        m = re.search(r"(\d{4})", str(path))
    if m:
        df.attrs["inferred_year"] = int(m.group(1))

    return df


def to_number(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def parse_period(label):
    """Turn column headers like 'JAN', 'Jan-2024', '2024', 'FEB 2023' into a date."""
    s = str(label).strip()
    d = pd.to_datetime(s, errors="coerce", format="mixed", dayfirst=False)
    return d


def clean_single_df(df, year=None, district_rows=False):
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

    if not district_rows:
        # Keep only rows whose fuel label mentions CNG (CNG ONLY, PETROL/CNG, etc.)
        long = long[long["label"].str.contains("cng", case=False, regex=True)]

    effective_year = year or df.attrs.get("inferred_year")

    def make_period(x):
        s = str(x).strip()
        if effective_year and re.fullmatch(r"[A-Za-z]{3,9}", s):
            s = f"{s} {effective_year}"
        return parse_period(s)

    long["period"] = long["period_raw"].apply(make_period)
    long = long.dropna(subset=["period"])
    long["period"] = pd.to_datetime(long["period"]).dt.strftime("%Y-%m-%d")
    long = long[["label", "period", "registrations"]].sort_values(["label", "period"])
    return long


def main():
    import glob
    import os

    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=None, help="File path or glob pattern")
    ap.add_argument("--dir", default=None, help="Directory containing export files")
    ap.add_argument("--header-row", type=int, default=0)
    ap.add_argument("--year", type=int, default=None, help="Year to attach when columns are bare month names")
    ap.add_argument("--district-rows", action="store_true", help="Row labels are RTOs/districts (already CNG-only)")
    ap.add_argument("--out", default="vahan_cng_tidy.csv")
    args = ap.parse_args()

    files = []
    if args.dir:
        files = sorted(glob.glob(os.path.join(args.dir, "*.xlsx")) + glob.glob(os.path.join(args.dir, "*.csv")))
    elif args.file:
        if "*" in args.file or "?" in args.file:
            files = sorted(glob.glob(args.file))
        else:
            files = [args.file]
    else:
        ap.error("Must provide either --file or --dir")

    all_dfs = []
    for f in files:
        df = load_raw(f, args.header_row)
        tidy = clean_single_df(df, year=args.year, district_rows=args.district_rows)
        all_dfs.append(tidy)

    combined = pd.concat(all_dfs, ignore_index=True).drop_duplicates(subset=["label", "period"]).sort_values(["label", "period"])

    # Ensure output directory exists if specified
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    combined.to_csv(args.out, index=False)
    print(f"\nSaved {len(combined)} rows -> {args.out}")
    print(combined.head(12).to_string(index=False))
    print(
        "\nREMINDER: these are NEW registrations per period (a flow), not the total fleet on the road. "
        "Build a cumulative sum from your earliest year if you want a fleet-size proxy."
    )


if __name__ == "__main__":
    main()
