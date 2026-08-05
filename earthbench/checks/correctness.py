"""Axis 2b: CORRECTNESS. Do the fields match reality?

Faithfulness (grounding.py) asks whether the prose follows from the fields.
This asks whether the fields follow from the world. They are independent, and
keeping them apart is the whole argument:

    San Francisco, /ask, "what city is this?"
      prose:   "Unincorporated"     <- perfectly faithful to the field
      field:   political_locality = "Unincorporated"  (confidence: medium)
      reality: San Francisco        <- the field is simply wrong

    Faithfulness 1.0. Correctness 0.0.

A citation tells you where a number came from. It does not tell you whether the
number is right. Mireye sells provenance as if it were trust, and it is not the
same thing.

Ground truth here comes only from authorities OUTSIDE Mireye.
"""

from ..oracles import california, federal


def check_locality(site, fetched: dict) -> dict | None:
    expected = site.truth.get("locality")
    if not expected:
        return None
    f = fetched.get("political_locality") or {}
    got = f.get("value")
    return {
        "field": "political_locality",
        "expected": expected,
        "got": got,
        "correct": got == expected,
        "confidence": f.get("confidence"),
        "oracle": "common knowledge (incorporated municipality)",
    }


def check_elevation(site, fetched: dict) -> dict | None:
    f = fetched.get("elevation") or {}
    got = f.get("value")
    if not isinstance(got, (int, float)):
        return None
    truth = federal.usgs_elevation_m(site.lat, site.lng)
    if truth is None:
        return None
    delta = abs(got - truth)
    return {
        "field": "elevation",
        "expected": round(truth, 2),
        "got": round(got, 2),
        # 3DEP vertical RMSE is ~1 m; anything inside that is agreement.
        "correct": delta <= 1.0,
        "delta_m": round(delta, 3),
        "confidence": f.get("confidence"),
        "oracle": "USGS EPQS, queried live",
    }


def check_flood_zone(site, fetched: dict) -> dict | None:
    f = fetched.get("fema_flood_zone") or {}
    got = f.get("value")
    truth = federal.fema_flood_zone(site.lat, site.lng)
    if got is None and truth is None:
        return None
    if truth is None:
        # The live NFHL query came back empty, so there is nothing to score
        # against. Marking this "incorrect" blames Mireye for the oracle being
        # down: it took fema_flood_zone from 58/58 to 58/68 on the 2026-08-05
        # run and read as a regression that had not happened.
        return {
            "field": "fema_flood_zone",
            "expected": None,
            "got": got,
            "correct": None,
            "skipped": "oracle unavailable: FEMA NFHL returned no zone for this point",
            "confidence": f.get("confidence"),
            "oracle": "FEMA NFHL, queried live",
        }
    return {
        "field": "fema_flood_zone",
        "expected": truth,
        "got": got,
        "correct": (got or None) == (truth or None),
        "confidence": f.get("confidence"),
        "oracle": "FEMA NFHL, queried live",
    }


def check_wildfire_authority(site, fetched: dict) -> dict | None:
    """The one that matters.

    Mireye's only wildfire field is FEMA NRI, an annualized event frequency
    published PER CENSUS TRACT. The map that actually decides whether a California
    homeowner keeps their insurance is the CAL FIRE Fire Hazard Severity Zone,
    mapped PER PARCEL, and Mireye does not carry it.

    This is not scored as right or wrong, because it is not a wrong number. It is
    a number that answers a different question than the one that gets asked. We
    record both so the report can put them side by side.
    """
    expected_zone = site.truth.get("fhsz")
    if not expected_zone:
        return None
    f = fetched.get("wildfire_annual_frequency") or {}
    return {
        "field": "wildfire_annual_frequency",
        "mireye_value": f.get("value"),
        "mireye_resolution": "census tract",
        "mireye_source": f.get("source"),
        "authority_value": expected_zone,
        "authority_resolution": "parcel",
        "authority_source": "CAL FIRE FHSZ",
        "correct": None,
        "note": "different question, not a wrong answer -- and not recoverable "
                "from Mireye's data at any resolution",
        "oracle": "CAL FIRE, queried live",
    }


CHECKS = [check_locality, check_elevation, check_flood_zone, check_wildfire_authority]


def score(site, fetched: dict) -> list[dict]:
    out = []
    for check in CHECKS:
        try:
            r = check(site, fetched)
        except Exception as exc:
            r = {"field": check.__name__, "error": str(exc)}
        if r:
            out.append(r)
    return out
