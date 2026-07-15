"""Axis 2a: FAITHFULNESS. Does the prose follow from the fields it cited?

This is deliberately NOT a correctness check. A perfectly faithful answer can be
completely wrong, if the field it faithfully repeats is wrong. That separation is
the point of the benchmark, and checks/correctness.py handles the other half.

Deterministic first: pull every number out of the answer and try to account for
it from the values in `fields_used`. A number in the prose that matches no cited
field is either derived (fine, if the derivation is sound) or invented (not fine).
The judge adjudicates the ambiguous ones; this pass catches the blatant ones and
gives the judge something to be checked against.
"""

import re

# A bare quantity: not glued to letters (NAVD88, 3DEP), not part of a larger token.
# The first version of this checker counted "88" out of "NAVD88" and the echoed
# input coordinates as unsupported claims, which made the score meaningless. The
# precision of the metric matters as much as the precision of the thing measured.
NUM = re.compile(r"(?<![A-Za-z0-9.\-])-?\d[\d,]*\.?\d*(?![A-Za-z0-9])")


def _non_claims(question: str, lat: float, lng: float, fetched: dict) -> set[float]:
    """Numbers in the prose that are not assertions about the world.

    Three kinds, all principled rather than hardcoded:
      - the coordinates we passed in, echoed back
      - numbers restated from the question
      - numbers that live inside the PROVENANCE of a cited field (source names,
        dataset vintages, methodology notes). "USGS 3DEP 1/3 arc-second ~10m" is
        a citation, not a claim, so its 3, 1, and 10 are not claims either.
    """
    out = {round(lat, 6), round(lng, 6), round(abs(lat), 6), round(abs(lng), 6)}
    for n in _numbers(question or ""):
        out.add(n)
    for f in fetched.values():
        meta = " ".join(str(f.get(k) or "") for k in
                        ("source", "source_url", "dataset_vintage", "notes", "unit"))
        for n in _numbers(meta):
            out.add(n)
    return out

# Answers routinely restate a value in different units than the field carries.
UNIT_EQUIVALENTS = [
    (1.0, ""),            # same
    (3.280839895, "m->ft"),
    (0.3048, "ft->m"),
    (0.001, "m->km"),
    (1000.0, "km->m"),
    (0.000621371, "m->mi"),
    (100.0, "frac->pct"),
    (0.01, "pct->frac"),
]


def _numbers(text: str) -> list[float]:
    out = []
    for m in NUM.finditer(text or ""):
        try:
            out.append(float(m.group().replace(",", "")))
        except ValueError:
            pass
    return out


def _accounted(n: float, values: list[float], rel_tol=0.02) -> str | None:
    """Can this number in the prose be explained by some cited field value?"""
    for v in values:
        for factor, label in UNIT_EQUIVALENTS:
            conv = v * factor
            if conv == 0:
                if abs(n) < 1e-9:
                    return label or "exact"
                continue
            if abs(n - conv) <= abs(conv) * rel_tol:
                return label or "exact"
            # rounding: the prose says 13.2 for a field value of 13.15
            if round(conv, 1) == round(n, 1) or round(conv) == round(n):
                return (label or "exact") + "+rounded"
    return None


def _sig_figs(s: str) -> int:
    s = s.lstrip("-0.")
    return len(s.replace(".", "").rstrip("0")) or 1


# Absolute vertical accuracy of the USGS 3DEP 1/3 arc-second seamless DEM:
# 0.82 m RMSE across the conterminous US as of 2022, measured against ~25,000
# NOAA National Geodetic Survey OPUS points. It was 1.55 m in 2013, and it still
# varies substantially by location with source quality, relief, and land cover.
#   https://www.usgs.gov/faqs/what-vertical-accuracy-3d-elevation-program-3dep-dems
#
# Mireye sources `elevation` from this DEM and reports it to the centimetre.
# Their own homepage prints "13.15 meters". Two decimal places on a value whose
# error is measured in tens of centimetres is not precision; it is decoration.
# And there is no error bar anywhere in the field envelope to say otherwise, so
# an agent consuming it has no way to know.
DEM_VERTICAL_RMSE_M = 0.82


def precision_inflation(fetched: dict) -> list[dict]:
    """Does a field report more precision than its source can support?

    Mireye's own homepage prints `elevation = 13.15 meters`, sourced from USGS
    3DEP -- a 10 m DEM with roughly a metre of vertical error. Two decimal places
    on a value accurate to +/- 1 m is not precision, it is decoration, and an
    agent reading it will treat it as exact. There is no error bar anywhere in
    the field envelope to tell it otherwise.
    """
    flags = []
    elev = fetched.get("elevation")
    if elev and isinstance(elev.get("value"), float):
        v = elev["value"]
        decimals = len(str(v).split(".")[1]) if "." in str(v) else 0
        if decimals >= 1:
            flags.append({
                "field": "elevation",
                "reported": v,
                "reported_decimals": decimals,
                "source_rmse_m": DEM_VERTICAL_RMSE_M,
                "issue": "reported precision exceeds source accuracy; no error bar in envelope",
            })
    return flags


def score(answer: str, fetched: dict, question: str = "", lat: float = 0.0, lng: float = 0.0) -> dict:
    """fetched: {field_name: envelope} for exactly the fields /ask said it used."""
    values = [f.get("value") for f in fetched.values()
              if isinstance(f.get("value"), (int, float))]
    strings = [str(f.get("value")).lower() for f in fetched.values()
               if isinstance(f.get("value"), str)]

    skip = _non_claims(question, lat, lng, fetched)

    unaccounted, accounted = [], []
    for n in _numbers(answer):
        if n in skip or round(n, 6) in skip:
            continue
        how = _accounted(n, values)
        (accounted if how else unaccounted).append({"n": n, "via": how})

    text = (answer or "").lower()
    echoed = [s for s in strings if s and s in text]

    total = len(accounted) + len(unaccounted)
    return {
        "n_claims": total,
        "n_unaccounted": len(unaccounted),
        "unaccounted": unaccounted,
        "faithfulness_numeric": round(len(accounted) / total, 3) if total else None,
        "categorical_echoed": echoed,
        "precision_flags": precision_inflation(fetched),
    }
