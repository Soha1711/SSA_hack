"""
geocode_stations.py - Geocoding module for Gujarat Gas CNG stations.

Nominatim (OpenStreetMap) geocoding with strict quality controls:
1. Max 1 request per second rate limiting.
2. Comprehensive file caching in data/interim/geocode_cache.json.
3. 3-tier waterfall matching:
   - Tier 1: Full address (High confidence)
   - Tier 2: Station name + Locality + District (Medium confidence)
   - Tier 3: Pincode + District (Low confidence)
4. Validation constraints:
   - Must lie inside Gujarat bounding box: [20.0, 24.8] N, [68.0, 74.5] E.
   - Must lie within ~25 km of the expected city centre.
   - Strict rejection of out-of-bounds results; never guesses or places stations at city centres.
5. Outputs:
   - data/processed/stations_geocoded.csv
   - data/processed/geocode_review.csv (unmatched and low-confidence stations)
"""

import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# City centres for distance-to-centre validation (WGS84)
CITY_CENTRES: Dict[str, Tuple[float, float]] = {
    "surat": (21.1702, 72.8311),
    "rajkot": (22.3039, 70.8022),
    "ahmedabad": (23.0225, 72.5714),
    "vadodara": (22.3072, 73.1812),
}

# Gujarat administrative bounding box
GUJARAT_BBOX = {
    "min_lat": 20.0,
    "max_lat": 24.8,
    "min_lon": 68.0,
    "max_lon": 74.5,
}

MAX_CITY_DIST_KM = 25.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in kilometers."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2.0) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0) ** 2
    c = 2.0 * asin(sqrt(a))
    return c * 6371.0


class NominatimGeocoder:
    """Nominatim geocoder with disk caching and 1 request/sec rate limiting."""

    def __init__(
        self,
        cache_path: str = "data/interim/geocode_cache.json",
        user_agent: str = "CNGDemandPlanner-PS000002/1.0 (Gujarat Gas Academic Siting Research; team: TM000846)",
        delay_sec: float = 1.1,
    ):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.delay_sec = delay_sec
        self.last_request_time = 0.0
        self.cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_path.is_file():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load cache from {self.cache_path}: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save cache: {e}")

    def query(self, query_str: str) -> List[Dict[str, Any]]:
        """Query Nominatim with caching and rate limiting."""
        query_clean = " ".join(query_str.split()).strip()
        if not query_clean:
            return []

        # Check cache
        if query_clean in self.cache:
            return self.cache[query_clean]

        # Enforce rate limit
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay_sec:
            time.sleep(self.delay_sec - elapsed)

        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": self.user_agent}
        params = {
            "q": query_clean,
            "format": "json",
            "limit": 3,
            "countrycodes": "in",
            "addressdetails": 1,
        }

        try:
            r = requests.get(url, params=params, headers=headers, timeout=12)
            self.last_request_time = time.time()
            if r.status_code == 200:
                data = r.json()
                self.cache[query_clean] = data
                self._save_cache()
                return data
            else:
                print(f"Nominatim returned HTTP {r.status_code} for query: '{query_clean}'")
                return []
        except Exception as e:
            print(f"Network error querying Nominatim for '{query_clean}': {e}")
            self.last_request_time = time.time()
            return []


def clean_address_text(address: str) -> str:
    """Remove boilerplate surveying/legal terms from Indian CGD address records."""
    text = address
    # Remove Dist / Taluka mentions
    text = re.sub(r"Dist(?:rict)?\s*:\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"Tal(?:uka)?\s*:\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"TA\s*:\s*[^,]+", "", text, flags=re.I)
    # Remove Plot / Survey / FP / Block boilerplate
    text = re.sub(r"Plot\s+No\s*:\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"Survey\s+No\s*:\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"Block\s+No\s*:\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"T\.?P\.?\s*No\.?\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"F\.?P\.?\s*No\.?\s*[^,]+", "", text, flags=re.I)
    text = re.sub(r"\bPart\s+[A-Z]\b", "", text, flags=re.I)
    # Clean whitespace and trailing punctuation
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",\s*,+", ",", text)
    return text.strip(" ,.-")


def extract_locality(address: str, district: str) -> str:
    """Extract prominent locality, suburb, or major road from the address text."""
    # Split by comma
    parts = [p.strip() for p in address.split(",") if p.strip()]
    candidates = []
    
    for p in parts:
        # Skip pure administrative tags or boilerplate
        if re.search(r"^(dist|tal|taluka|plot|survey|block|nr\.|opp\.)", p, re.I):
            continue
        # Remove pincode if attached
        p_clean = re.sub(r"\b3\d{5}\b", "", p).strip(" -")
        if p_clean and p_clean.lower() != district.lower() and len(p_clean) > 2:
            candidates.append(p_clean)
            
    if candidates:
        # Return first meaningful locality/landmark segment
        return candidates[0]
    return ""


def validate_coordinates(
    lat: float, lon: float, city: str
) -> Tuple[bool, float, str]:
    """
    Verify coordinates are inside Gujarat bounding box and within ~25 km of city centre.
    """
    in_bbox = (
        GUJARAT_BBOX["min_lat"] <= lat <= GUJARAT_BBOX["max_lat"]
        and GUJARAT_BBOX["min_lon"] <= lon <= GUJARAT_BBOX["max_lon"]
    )
    if not in_bbox:
        return False, 0.0, "Outside Gujarat administrative bounding box"

    c_lat, c_lon = CITY_CENTRES.get(city.lower(), (0.0, 0.0))
    if c_lat == 0.0:
        return True, 0.0, "Accepted (no city centre specified)"

    dist_km = haversine_km(lat, lon, c_lat, c_lon)
    if dist_km > MAX_CITY_DIST_KM:
        return False, dist_km, f"Outside {MAX_CITY_DIST_KM} km of {city} centre (dist = {dist_km:.1f} km)"

    return True, dist_km, "Valid"


def geocode_station_record(
    station_name: str,
    raw_address: str,
    district: str,
    pincode: str,
    city: str,
    geocoder: NominatimGeocoder,
) -> Dict[str, Any]:
    """
    Execute 3-tier waterfall geocoding on a single station record.
    """
    c_lat, c_lon = CITY_CENTRES.get(city.lower(), (0.0, 0.0))
    pin_str = str(pincode).split(".")[0].strip() if pd.notna(pincode) else ""
    cleaned_addr = clean_address_text(raw_address)
    locality = extract_locality(raw_address, district)

    # ----------------------------------------------------
    # TIER 1: Full Address (High confidence)
    # ----------------------------------------------------
    t1_queries = []
    if cleaned_addr:
        t1_queries.append(f"{cleaned_addr}, {district}, Gujarat, India")
    
    for q in t1_queries:
        res = geocoder.query(q)
        if res:
            for item in res:
                lat, lon = float(item["lat"]), float(item["lon"])
                valid, dist, reason = validate_coordinates(lat, lon, city)
                if valid:
                    return {
                        "lat": lat,
                        "lon": lon,
                        "match_method": "full_address",
                        "confidence": "high",
                        "geocoded": True,
                        "dist_to_centre_km": round(dist, 2),
                        "review_reason": None,
                    }

    # ----------------------------------------------------
    # TIER 2: Station Name + Locality + District (Medium confidence)
    # ----------------------------------------------------
    t2_queries = []
    # Clean station name (remove GGL / Gujarat Gas prefixes)
    st_clean = re.sub(r"^(GGL|Gujarat Gas)\s*", "", station_name, flags=re.I).strip()
    
    if locality and st_clean and len(st_clean) > 3:
        t2_queries.append(f"{st_clean}, {locality}, {district}, Gujarat, India")
    if locality:
        t2_queries.append(f"{locality}, {district}, Gujarat, India")
    if locality and pin_str:
        t2_queries.append(f"{locality}, {pin_str}, Gujarat, India")

    for q in t2_queries:
        res = geocoder.query(q)
        if res:
            for item in res:
                lat, lon = float(item["lat"]), float(item["lon"])
                valid, dist, reason = validate_coordinates(lat, lon, city)
                if valid:
                    return {
                        "lat": lat,
                        "lon": lon,
                        "match_method": "name_locality_district",
                        "confidence": "medium",
                        "geocoded": True,
                        "dist_to_centre_km": round(dist, 2),
                        "review_reason": None,
                    }

    # ----------------------------------------------------
    # TIER 3: Pincode + District (Low confidence)
    # ----------------------------------------------------
    if pin_str and len(pin_str) == 6:
        q_pin = f"{pin_str}, {district}, Gujarat, India"
        res = geocoder.query(q_pin)
        if res:
            for item in res:
                lat, lon = float(item["lat"]), float(item["lon"])
                valid, dist, reason = validate_coordinates(lat, lon, city)
                if valid:
                    return {
                        "lat": lat,
                        "lon": lon,
                        "match_method": "pincode_district",
                        "confidence": "low",
                        "geocoded": True,
                        "dist_to_centre_km": round(dist, 2),
                        "review_reason": "Matched at pincode/postcode centroid (low spatial precision)",
                    }
                else:
                    last_invalid_reason = reason
        else:
            last_invalid_reason = "Pincode query returned no Nominatim match"
    else:
        last_invalid_reason = "No valid 6-digit pincode available"

    # Unmatched
    return {
        "lat": None,
        "lon": None,
        "match_method": None,
        "confidence": "none",
        "geocoded": False,
        "dist_to_centre_km": None,
        "review_reason": last_invalid_reason if "last_invalid_reason" in locals() else "All geocoding tiers failed",
    }


def geocode_all_stations():
    """Geocode all stations across Surat, Rajkot, Ahmedabad, and Vadodara."""
    print("=" * 65)
    print("GUJARAT GAS STATION GEOCODING PIPELINE (NOMINATIM)")
    print("=" * 65)

    geocoder = NominatimGeocoder()
    cities = ["surat", "rajkot", "ahmedabad", "vadodara"]
    
    all_results = []
    review_records = []
    city_stats = {}

    for city in cities:
        csv_path = Path(f"data/raw/station_addresses_{city}.csv")
        if not csv_path.is_file():
            print(f"Skipping {city}: {csv_path} not found.")
            continue

        df = pd.read_csv(csv_path)
        print(f"\nProcessing {city.upper()} ({len(df)} stations)...")

        matched_count = 0
        high_count = 0
        med_count = 0
        low_count = 0
        unmatched_count = 0

        for idx, row in df.iterrows():
            st_name = str(row.get("station_name", ""))
            addr = str(row.get("address", ""))
            dist = str(row.get("district", city.title()))
            pin = row.get("pincode", "")

            geo_res = geocode_station_record(
                station_name=st_name,
                raw_address=addr,
                district=dist,
                pincode=pin,
                city=city,
                geocoder=geocoder,
            )

            record = {
                "city": city.title(),
                "station_name": st_name,
                "address": addr,
                "lat": geo_res["lat"],
                "lon": geo_res["lon"],
                "match_method": geo_res["match_method"],
                "confidence": geo_res["confidence"],
                "geocoded": geo_res["geocoded"],
            }
            all_results.append(record)

            if geo_res["geocoded"]:
                matched_count += 1
                if geo_res["confidence"] == "high":
                    high_count += 1
                elif geo_res["confidence"] == "medium":
                    med_count += 1
                elif geo_res["confidence"] == "low":
                    low_count += 1

            if not geo_res["geocoded"] or geo_res["confidence"] == "low":
                review_records.append({
                    "city": city.title(),
                    "station_name": st_name,
                    "address": addr,
                    "district": dist,
                    "pincode": pin,
                    "match_method": geo_res["match_method"],
                    "confidence": geo_res["confidence"],
                    "geocoded": geo_res["geocoded"],
                    "dist_to_centre_km": geo_res["dist_to_centre_km"],
                    "reason": geo_res["review_reason"],
                })

        rate = (matched_count / len(df)) * 100.0
        city_stats[city.title()] = {
            "Total": len(df),
            "Geocoded": matched_count,
            "Success Rate (%)": round(rate, 1),
            "High Conf": high_count,
            "Medium Conf": med_count,
            "Low Conf": low_count,
            "Unmatched": len(df) - matched_count,
        }

    # Save output files
    out_geocoded_csv = Path("data/processed/stations_geocoded.csv")
    out_geocoded_csv.parent.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame(all_results)
    df_out.to_csv(out_geocoded_csv, index=False)
    print(f"\nSaved geocoded stations to {out_geocoded_csv.resolve()}")

    out_review_csv = Path("data/processed/geocode_review.csv")
    df_review = pd.DataFrame(review_records)
    df_review.to_csv(out_review_csv, index=False)
    print(f"Saved review list to {out_review_csv.resolve()} ({len(df_review)} entries)")

    # Print summary table
    stats_df = pd.DataFrame.from_dict(city_stats, orient="index")
    print("\nGeocoding Summary Table by City:")
    print(stats_df.to_string())
    print("=" * 65)


if __name__ == "__main__":
    geocode_all_stations()
