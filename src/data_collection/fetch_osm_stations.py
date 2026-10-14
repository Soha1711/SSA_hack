"""
Step 1: Download CNG fuel stations in Gujarat from OpenStreetMap (Overpass API).

Run:  pip install requests pandas
      python 01_fetch_osm_stations.py

Output: osm_cng_stations_gujarat.csv  (one row per station)
"""
import re
import time
import requests
import pandas as pd

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Gujarat = admin_level 4 relation. Pull anything tagged as a fuel station that
# sells CNG, plus stations whose name/brand/operator mentions a CNG operator.
QUERY = r"""
[out:json][timeout:180];
area["ISO3166-2"="IN-GJ"]["boundary"="administrative"]->.gj;
(
  nwr["amenity"="fuel"]["fuel:cng"="yes"](area.gj);
  nwr["amenity"="fuel"]["name"~"CNG|Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|Indian Oil.Adani|IOAGPL",i](area.gj);
  nwr["amenity"="fuel"]["operator"~"Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|IOAGPL",i](area.gj);
  nwr["amenity"="fuel"]["brand"~"Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|IOAGPL",i](area.gj);
);
out center tags;
"""

QUERY_BBOX = r"""
[out:json][timeout:180];
(
  nwr["amenity"="fuel"]["fuel:cng"="yes"](20.0,68.0,24.8,74.6);
  nwr["amenity"="fuel"]["name"~"CNG|Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|Indian Oil.Adani|IOAGPL",i](20.0,68.0,24.8,74.6);
  nwr["amenity"="fuel"]["operator"~"Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|IOAGPL",i](20.0,68.0,24.8,74.6);
  nwr["amenity"="fuel"]["brand"~"Gujarat Gas|Sabarmati|Adani Total|Torrent|Think Gas|IOAGPL",i](20.0,68.0,24.8,74.6);
);
out center tags;
"""

HEADERS = {
    "User-Agent": "GujaratCNGDemandPlanner/1.0 (academic_hackathon_project)"
}


def fetch():
    last_err = None
    # Try mirrors first with standard QUERY, then with QUERY_BBOX if area query fails
    for q_name, q_text in [("area query", QUERY), ("bbox fallback query", QUERY_BBOX)]:
        for url in OVERPASS_URLS:
            try:
                print(f"Querying {url} with {q_name} ...")
                r = requests.post(url, data={"data": q_text}, headers=HEADERS, timeout=240)
                r.raise_for_status()
                return r.json()["elements"]
            except Exception as e:  # try next mirror
                last_err = e
                print("  failed:", e)
                time.sleep(3)
    raise RuntimeError(f"All Overpass mirrors failed: {last_err}")


def classify_operator(row):
    """Label which CGD company a station belongs to (best effort from tags)."""
    text = " ".join(str(row.get(k, "")) for k in ("name", "brand", "operator")).lower()
    if re.search(r"gujarat\s*gas|\bggcl\b|\bgujaratgas\b", text):
        return "Gujarat Gas"
    if "sabarmati" in text:
        return "Sabarmati Gas"
    if "adani" in text or "ioagpl" in text or "indian oil" in text and "adani" in text:
        return "Adani Total / IOAGPL"
    if "torrent" in text:
        return "Torrent Gas"
    if "think gas" in text:
        return "Think Gas"
    return "Unknown / other"


def main():
    elements = fetch()
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:  # way / relation -> centre point
            c = el.get("center", {})
            lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        rows.append(
            {
                "osm_type": el["type"],
                "osm_id": el["id"],
                "lat": lat,
                "lon": lon,
                "name": tags.get("name"),
                "brand": tags.get("brand"),
                "operator": tags.get("operator"),
                "fuel_cng": tags.get("fuel:cng"),
                "opening_hours": tags.get("opening_hours"),
                "start_date": tags.get("start_date"),
                "addr_city": tags.get("addr:city"),
                "addr_district": tags.get("addr:district"),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("No stations returned - check the query / try again later.")

    df["cgd_company"] = df.apply(classify_operator, axis=1)

    # Remove exact duplicates (same OSM object) and near-duplicates (<30 m apart,
    # same operator) which usually mean a node + a building outline of the same site.
    n_raw = len(df)
    df = df.drop_duplicates(subset=["osm_type", "osm_id"])
    n_exact_dups = n_raw - len(df)

    df = df.sort_values(["cgd_company", "lat", "lon"]).reset_index(drop=True)
    keep = []
    seen = []
    for i, r in df.iterrows():
        dup = False
        for (la, lo, comp) in seen:
            if comp == r["cgd_company"] and abs(la - r["lat"]) < 0.0003 and abs(lo - r["lon"]) < 0.0003:
                dup = True
                break
        if not dup:
            keep.append(i)
            seen.append((r["lat"], r["lon"], r["cgd_company"]))
    before_near = len(df)
    df = df.loc[keep].reset_index(drop=True)
    n_near_dups = before_near - len(df)
    n_total_dups = n_exact_dups + n_near_dups

    # Keep only points inside a rough Gujarat bounding box (guards against bad tags)
    before_bbox = len(df)
    df = df[df["lat"].between(20.0, 24.8) & df["lon"].between(68.0, 74.6)]
    n_outside_bbox = before_bbox - len(df)

    df.to_csv("osm_cng_stations_gujarat.csv", index=False)
    print(f"\nTotal raw elements fetched: {n_raw}")
    print(f"Exact duplicates removed: {n_exact_dups}")
    print(f"Near-duplicates (<30m) removed: {n_near_dups}")
    print(f"Total duplicates removed: {n_total_dups}")
    print(f"Points outside Gujarat bounding box: {n_outside_bbox}")
    print(f"Saved {len(df)} stations -> osm_cng_stations_gujarat.csv")
    print("\nCounts per CGD company:")
    print(df["cgd_company"].value_counts())
    gg_count = (df["cgd_company"] == "Gujarat Gas").sum()
    coverage_pct = (gg_count / 560.0) * 100
    print(f"\nGujarat Gas stations in OSM: {gg_count} vs ~560 reported ({coverage_pct:.2f}% coverage)")


if __name__ == "__main__":
    main()
