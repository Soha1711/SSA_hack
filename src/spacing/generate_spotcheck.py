"""
generate_spotcheck.py
---------------------
Generate geocode_spotcheck.csv listing 15 random medium-confidence stations
with direct Google Maps links for manual verification.
"""

from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GEOCODED_CSV = PROJECT_ROOT / "data" / "processed" / "stations_geocoded.csv"
OUTPUT_PROCESSED = PROJECT_ROOT / "data" / "processed" / "geocode_spotcheck.csv"
OUTPUT_ROOT = PROJECT_ROOT / "geocode_spotcheck.csv"

def generate_spotcheck(seed: int = 42):
    df = pd.read_csv(GEOCODED_CSV)
    
    # Identify unique coordinates among all geocoded stations
    geocoded_pts = df[df["geocoded"] == True]
    pt_counts = geocoded_pts.groupby(["lat", "lon"]).size()
    dup_coords = pt_counts[pt_counts > 1].index
    
    # Clean subset: high or medium confidence, strictly unique coordinates
    df_clean = df[
        df["geocoded"]
        & df["confidence"].isin(["high", "medium"])
        & (~df.set_index(["lat", "lon"]).index.isin(dup_coords))
    ].copy().reset_index(drop=True)
    
    # Filter to medium confidence stations retained in the analysis
    df_med = df_clean[df_clean["confidence"] == "medium"].copy()
    
    # Sample 15 random medium-confidence stations
    sample_df = df_med.sample(n=15, random_state=seed).copy()
    
    sample_df["google_maps_link"] = sample_df.apply(
        lambda r: f"https://www.google.com/maps?q={r['lat']:.6f},{r['lon']:.6f}", axis=1
    )
    
    out_cols = ["city", "station_name", "address", "lat", "lon", "google_maps_link"]
    spotcheck = sample_df[out_cols].rename(columns={"station_name": "name"})
    
    spotcheck.to_csv(OUTPUT_PROCESSED, index=False)
    spotcheck.to_csv(OUTPUT_ROOT, index=False)
    print(f"Saved spotcheck to {OUTPUT_PROCESSED} and {OUTPUT_ROOT} ({len(spotcheck)} rows)")
    return spotcheck

if __name__ == "__main__":
    spot = generate_spotcheck()
    print(spot.to_string(index=False))
