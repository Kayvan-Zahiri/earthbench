"""Thin client for Mireye's /v1/fetch and /v1/ask, plus free address geocoding."""

import json
import time
import threading
import os
import pathlib
import urllib.parse
import urllib.error
import urllib.request

API = "https://api.mireye.com"
TIMEOUT_S = 90

# The Census geocoder is free, keyless, and is the same one Mireye uses
# internally (US_CENSUS_GEOCODER appears in their field catalog).
CENSUS = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# The federal fields that bear on a California wildfire-insurance decision.
# This is everything Mireye can contribute to the question.
WILDFIRE_FIELDS = [
    "wildfire_annual_frequency",
    "tree_canopy_pct",
    "ndvi_current",
    "lcms_class",
    "slope_degrees",
    "aspect_cardinal",
    "elevation",
    "nearest_fire_station_distance_m",
    "nearest_fire_station_name",
    "housing_units_density_per_km2",
    "nearest_road_distance_m",
    "parcel_address",
    "political_locality",
    "political_county",
]


def _key() -> str:
    key = os.environ.get("MIREYE_API_KEY")
    if key:
        return key
    for candidate in (pathlib.Path(".env"), pathlib.Path.home() / "Desktop/jobs/.env"):
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("MIREYE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("MIREYE_API_KEY not set (env or .env)")


# The free plan allows 20 requests/minute. Without pacing, a full benchmark run
# fires 225 requests as fast as it can and every one comes back 429, which used
# to look like a completed run because each failure was caught per-sample.
_RPM = 20
_MIN_GAP = 60.0 / _RPM
_rate_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    """Space calls to the documented rate limit, across threads."""
    global _last_call
    with _rate_lock:
        gap = time.monotonic() - _last_call
        if gap < _MIN_GAP:
            time.sleep(_MIN_GAP - gap)
        _last_call = time.monotonic()


def _post(path: str, payload: dict, *, attempts: int = 4) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_key()}"},
    )
    for attempt in range(attempts):
        _throttle()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            # 429 is the one worth waiting out; anything else is a real answer.
            if exc.code != 429 or attempt == attempts - 1:
                raise
            wait = float(exc.headers.get("Retry-After") or 0) or _MIN_GAP * (2 ** attempt)
            time.sleep(wait)
    raise RuntimeError("unreachable")


NOMINATIM = "https://nominatim.openstreetmap.org/search"


def _geocode_census(address: str):
    params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    url = f"{CENSUS}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = json.loads(resp.read())
    matches = body.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    c = matches[0]["coordinates"]
    return float(c["y"]), float(c["x"])


def _geocode_osm(address: str):
    # The Census geocoder only knows addresses in its own address-range files and
    # misses plenty of real streets, so OSM is the fallback.
    params = {"q": address, "format": "json", "limit": "1", "countrycodes": "us"}
    req = urllib.request.Request(
        f"{NOMINATIM}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "mireye-ca-gap/0.1 (take-home; contact via github)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
    if not body:
        return None
    return float(body[0]["lat"]), float(body[0]["lon"])


def geocode(address: str) -> tuple[float, float]:
    for backend in (_geocode_census, _geocode_osm):
        try:
            hit = backend(address)
        except Exception:
            hit = None
        if hit:
            return hit
    raise ValueError(f"could not geocode: {address!r}")


def fetch(lat: float, lng: float, fields: list[str] | None = None) -> dict:
    """Mireye's federal fields. Returns {field_name: envelope}."""
    body = _post("/v1/fetch", {"lat": lat, "lng": lng, "fields": fields or WILDFIRE_FIELDS})
    return body.get("fields", {})


def ask(lat: float, lng: float, question: str) -> dict:
    return _post("/v1/ask", {"lat": lat, "lng": lng, "question": question})
