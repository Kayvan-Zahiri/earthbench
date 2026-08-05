"""The guard: a fuel proxy is not a hazard rating.

Mireye's `wildfire_underwrite` preset is six fields:

    elevation, slope_degrees, lcms_class, tree_canopy_pct,
    ndvi_current, ndvi_change_5y

Every one describes what is on the ground right now. None is a hazard rating.
At Paradise, California the preset returns slope 4.1 degrees, canopy 1.0%,
land cover Grass/Forb/Herb, NDVI 0.109. Read at face value that is a low-fuel
site. CAL FIRE rates the same coordinate Very High.

The canopy is 1% because the Camp Fire destroyed the town in November 2018 and
killed 85 people. The preset is measuring the burn scar and an agent that trusts
it concludes the safest thing about the parcel is the fire that already happened.

So this module does two things:

  1. Refuses to state a hazard verdict from proxies alone. A verdict needs a
     regulatory rating, and Mireye has none for wildfire.
  2. Detects the burn-scar signature specifically, so "low fuel" is reported as
     suspicious rather than reassuring when it looks like aftermath.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

# The benchmark's oracles live one package up and already speak to CAL FIRE,
# CGS and FEMA. Reuse rather than reimplement.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

WILDFIRE_PROXIES = (
    "elevation",
    "slope_degrees",
    "lcms_class",
    "tree_canopy_pct",
    "ndvi_current",
    "ndvi_change_5y",
)

#: Land cover classes that are consistent with a recent burn, not just open land.
_SPARSE_COVER = {"grass/forb/herb", "barren", "shrubs", "sparse"}


@dataclass
class Verdict:
    """A hazard call, or an explicit refusal to make one."""

    decided: bool
    rating: str | None
    basis: str
    provenance: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def line(self) -> str:
        if not self.decided:
            return f"NO VERDICT — {self.basis}"
        return f"{self.rating} — {self.basis}"


def _val(fields: dict, name: str):
    v = fields.get(name)
    if isinstance(v, dict):
        return v.get("value")
    return v


def proxies_uninformative(fields: dict) -> str | None:
    """Are the fuel proxies incapable of separating safety from aftermath here?

    This started life as a burn-scar detector and the regression suite killed
    that claim. Measured across seven California sites, low canopy + low NDVI +
    sparse cover fires on Paradise, Santa Rosa and Redding, which all burned,
    and also on downtown San Francisco, which is pavement:

        Redding        canopy 1.0  ndvi  0.011  Barren or Impervious   burned 2018
        San Francisco  canopy 1.0  ndvi -0.017  Barren or Impervious   never burned

    Those rows are not meaningfully different, and `lcms_class` merges the two
    cases into one label. So the honest reading is not "this burned" but "these
    six fields cannot tell whether it burned," which is the thing an underwriter
    must not gloss over. Separating them needs fire perimeter history, which is
    not in the catalog.
    """
    canopy = _val(fields, "tree_canopy_pct")
    ndvi = _val(fields, "ndvi_current")
    cover = str(_val(fields, "lcms_class") or "").lower()

    if canopy is None or ndvi is None:
        return None
    if canopy <= 5.0 and ndvi <= 0.25 and any(c in cover for c in _SPARSE_COVER):
        return (
            f"canopy {canopy}%, NDVI {ndvi:.3f}, cover '{_val(fields, 'lcms_class')}'. "
            "These values are equally consistent with a burn scar, with bare ground "
            "that never carried fuel, and with pavement. The catalog cannot separate "
            "them, so this is not evidence of low hazard in either direction."
        )
    return None


def assess(lat: float, lng: float, fields: dict, *, authoritative=None) -> Verdict:
    """Decide wildfire hazard, or refuse.

    `authoritative` is a callable (lat, lng) -> dict of regulatory ratings, so
    the caller supplies the outside source. Nothing here infers hazard from the
    Mireye proxies, by design.
    """
    warnings: list[str] = []
    scar = proxies_uninformative(fields)
    if scar:
        warnings.append(scar)

    present = [f for f in WILDFIRE_PROXIES if _val(fields, f) is not None]
    if authoritative is None:
        return Verdict(
            decided=False,
            rating=None,
            basis=(
                f"{len(present)} fuel and terrain proxies available and no hazard rating. "
                "Mireye's catalog has no fire_hazard_severity_zone, burn_probability or "
                "wildfire_risk_to_homes, so a verdict cannot be grounded."
            ),
            warnings=warnings,
        )

    ratings = authoritative(lat, lng) or {}
    klass = ratings.get("calfire_fhsz_class") or {}
    value = klass.get("value") if isinstance(klass, dict) else klass

    if not value or (isinstance(klass, dict) and klass.get("status") not in (None, "ok")):
        return Verdict(
            decided=False,
            rating=None,
            basis="no regulatory hazard rating resolved for this coordinate",
            warnings=warnings,
        )

    prov = [
        {
            "field": "calfire_fhsz_class",
            "value": value,
            "source": klass.get("source") if isinstance(klass, dict) else "CALFIRE_FHSZ",
            "source_url": klass.get("source_url") if isinstance(klass, dict) else None,
            "confidence": klass.get("confidence") if isinstance(klass, dict) else None,
            "in_mireye": False,
        }
    ]

    basis = "CAL FIRE Fire Hazard Severity Zone, the map California insurers price against"
    if scar:
        basis += ". Mireye's fuel proxies read low at this site and disagree"

    return Verdict(decided=True, rating=str(value), basis=basis, provenance=prov, warnings=warnings)


def calfire(lat: float, lng: float) -> dict:
    """Authoritative wildfire rating from CAL FIRE, outside Mireye."""
    from earthbench.oracles import california

    return california.fetch_fhsz(lat, lng)
