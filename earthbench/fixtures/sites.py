"""Benchmark sites, chosen to stress specific seams.

Every site carries ground truth from an authority Mireye does NOT ingest, so the
harness is scoring against something independent rather than against itself.

Sources of truth:
  CAL FIRE FHSZ     state, and absent from Mireye's 255 fields
  CGS seismic       state, and absent from Mireye
  FEMA NFHL         federal, queried directly rather than through Mireye
  USGS EPQS         federal, queried live rather than through Mireye's cache
  common knowledge  e.g. San Francisco is an incorporated city
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Site:
    id: str
    lat: float
    lng: float
    why: str
    truth: dict = field(default_factory=dict)


SITES = [
    Site(
        "sf_marina", 37.8030, -122.4360,
        "SF Marina. Built on 1906 rubble fill; liquefied in Loma Prieta. Dense urban.",
        {"locality": "San Francisco", "in_liquefaction_zone": True, "fhsz": "NonWildland"},
    ),
    Site(
        "sf_mission", 37.7599, -122.4148,
        "SF Mission. Urban control for the locality bug.",
        {"locality": "San Francisco"},
    ),
    Site(
        "oakland_flats", 37.8280, -122.2560,
        "Oakland flats. Low, urban, no wildland fire hazard.",
        {"locality": "Oakland", "fhsz": "NonWildland"},
    ),
    Site(
        "oakland_hills_moderate", 37.8530, -122.2260,
        "Oakland hills, lower slope. SAME census tract as oakland_hills_high, "
        "but CAL FIRE puts it in a different hazard zone.",
        {"locality": "Oakland", "fhsz": "Moderate", "tract": "06001400100"},
    ),
    Site(
        "oakland_hills_high", 37.8556, -122.2237,
        "Oakland hills, 1991 Tunnel Fire footprint. SAME census tract as "
        "oakland_hills_moderate. This pair is the resolution test: FEMA NRI is "
        "per tract, CAL FIRE is per parcel, so Mireye must give both the same number.",
        {"locality": "Oakland", "fhsz": "High", "tract": "06001400100"},
    ),
    Site(
        "oakland_ridge", 37.8610, -122.2160,
        "Oakland ridge. Very High hazard.",
        {"fhsz": "Very High"},
    ),
    Site(
        "paradise", 39.7486, -121.5798,
        "Paradise CA. 2018 Camp Fire killed 85 people. Post-fire, so canopy and NDVI "
        "read as LOW fuel -- a naive model calls this low risk. CGS never mapped it "
        "for seismic hazard, so 'not in a liquefaction zone' is unknowable here.",
        {"locality": "Paradise", "fhsz": "Very High", "seismic_evaluated": False},
    ),
    Site(
        "guerneville", 38.5021, -122.9958,
        "Guerneville CA, on the Russian River. FEMA Zone AE -- a real Special Flood "
        "Hazard Area where a base flood elevation applies and floods happen most "
        "winters. This is where the bfe_margin question has teeth: a decisive field "
        "(fema_base_flood_elevation) genuinely exists to be fetched or missed.",
        {"flood_zone": "AE"},
    ),
    Site(
        "denver", 39.7392, -104.9903,
        "Denver. Non-California control, and the second city where Mireye's "
        "locality field fails.",
        {"locality": "Denver"},
    ),
    Site(
        "manhattan", 40.7128, -74.0060,
        "Lower Manhattan. The coordinate from Mireye's own homepage example.",
        {"locality": "New York"},
    ),
    Site(
        "rural_kansas", 39.0000, -95.0000,
        "Rural Kansas. Agricultural control, far from any California-specific issue.",
        {},
    ),
    Site(
        "pacific_ocean", 36.0000, -125.0000,
        "Open Pacific, inside Mireye's stated bounding box but not on land. "
        "Edge case: does it refuse, or invent?",
        {"on_land": False},
    ),
]

BY_ID = {s.id: s for s in SITES}

# The pair that proves the resolution gap. Mireye MUST return an identical
# wildfire number for both, because FEMA NRI is published per census tract.
# CAL FIRE puts them in different hazard zones. No post-processing recovers this.
TRACT_COLLISION = ("oakland_hills_moderate", "oakland_hills_high")
