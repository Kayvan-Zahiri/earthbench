"""Point-in-polygon lookups against public ArcGIS FeatureServers.

Every California state hazard layer we need (CAL FIRE, CGS) is published as an
ArcGIS FeatureServer, so one query function covers all of them.
"""

import json
import urllib.parse
import urllib.request

TIMEOUT_S = 30


class LayerUnavailable(Exception):
    """The upstream service failed. Distinct from 'the point is not in a zone'."""


def query_point(service_url: str, lat: float, lng: float) -> list[dict]:
    """Return the attributes of every polygon containing (lat, lng).

    An empty list means the point is genuinely outside every polygon in the
    layer. It does not mean the layer failed -- that raises LayerUnavailable.
    """
    params = {
        "geometry": f"{lng},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{service_url}/query?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read())
    except Exception as exc:
        raise LayerUnavailable(f"{service_url}: {exc}") from exc

    if "error" in body:
        raise LayerUnavailable(f"{service_url}: {body['error'].get('message')}")

    return [f.get("attributes", {}) for f in body.get("features", [])]
