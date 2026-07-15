"""Federal ground truth, queried directly.

Mireye also uses these sources. That is the point: we query them ourselves so
that when Mireye's cached answer diverges from the live authority, the harness
sees it. Scoring a system against its own cache proves nothing.
"""

import json
import urllib.parse
import urllib.request

TIMEOUT_S = 30

USGS_EPQS = "https://epqs.nationalmap.gov/v1/json"
FEMA_NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"


def usgs_elevation_m(lat: float, lng: float) -> float | None:
    """Live USGS 3DEP elevation, in metres.

    The service reports to centimetres. The underlying 1/3 arc-second DEM has a
    vertical RMSE around 1 metre, so that precision is not accuracy -- which is
    exactly the trap the bfe_margin question probes.
    """
    url = f"{USGS_EPQS}?{urllib.parse.urlencode({'x': lng, 'y': lat, 'units': 'Meters', 'wkid': 4326})}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read())
        value = body.get("value")
        return float(value) if value not in (None, "", -1000000) else None
    except Exception:
        return None


def fema_flood_zone(lat: float, lng: float) -> str | None:
    """Live FEMA National Flood Hazard Layer zone (layer 28 = Flood Hazard Zones)."""
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FLD_ZONE,ZONE_SUBTY,STATIC_BFE",
        "returnGeometry": "false",
        "f": "json",
    }
    try:
        with urllib.request.urlopen(f"{FEMA_NFHL}?{urllib.parse.urlencode(params)}", timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read())
        feats = body.get("features", [])
        if not feats:
            return None
        return feats[0].get("attributes", {}).get("FLD_ZONE")
    except Exception:
        return None
