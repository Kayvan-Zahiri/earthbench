"""Read Mireye's catalog the way an agent should: presets to pick fields,
interpretation_hints to get thresholds, null_meaning to explain a blank.

The benchmark measured an agent guessing field names out of a 255-field catalog
with no discovery tool, and 21 of 39 guesses (54%) named a field that did not
exist. The catalog is public and carries all of this, so the agent never guesses.
"""

from __future__ import annotations

import functools
import re

from . import client

# "Slope >15° materially raises wildfire spread risk" -> (">", 15.0, "wildfire spread risk")
_THRESHOLD = re.compile(
    r"(?P<op>[><]=?|above|below|under|over)\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>°|%|m\b|km\b|degrees?)?"
    r"(?P<tail>[^.;]{0,90})",
    re.I,
)
_OPS = {"above": ">", "over": ">", "below": "<", "under": "<"}


@functools.lru_cache(maxsize=1)
def _fields() -> tuple[dict, ...]:
    return tuple(client.catalog())


def by_name() -> dict[str, dict]:
    return {f["name"]: f for f in _fields()}


def exists(name: str) -> bool:
    return name in by_name()


def preset(name: str) -> list[str]:
    """Field names carrying a given preset, e.g. 'wildfire_underwrite'."""
    out = []
    for f in _fields():
        p = f.get("presets") or []
        p = p if isinstance(p, list) else [p]
        if name in p:
            out.append(f["name"])
    return sorted(out)


def presets() -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in _fields():
        p = f.get("presets") or []
        p = p if isinstance(p, list) else [p]
        for name in p:
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def hint(name: str) -> str:
    h = by_name().get(name, {}).get("interpretation_hints") or ""
    return h if isinstance(h, str) else str(h)


def null_meaning(name: str) -> str:
    n = by_name().get(name, {}).get("null_meaning") or ""
    return n if isinstance(n, str) else str(n)


def source_of(name: str) -> str:
    return by_name().get(name, {}).get("source") or "unknown"


def thresholds(name: str) -> list[dict]:
    """Numeric thresholds stated in a field's interpretation_hints.

    These are Mireye's own numbers, not ours. Using them means the agent's
    cutoffs are the vendor's documented ones and can be cited as such.
    """
    out = []
    for m in _THRESHOLD.finditer(hint(name)):
        op = m.group("op").lower()
        out.append(
            {
                "op": _OPS.get(op, op),
                "value": float(m.group("num")),
                "unit": (m.group("unit") or "").strip(),
                "means": m.group("tail").strip(" ,:-"),
            }
        )
    return out


def ghost_references(name: str) -> list[str]:
    """Field names a hint tells you to combine with that are not in the catalog.

    Real example: slope_degrees says "Combine with lcms_class and dist_to_wui_m
    for wildfire underwriting" and dist_to_wui_m does not exist. An agent that
    follows hints literally would request it and fail, which is exactly the
    failure mode the benchmark measured. Surfacing it lets the agent route the
    gap to a field request instead of a bad call.
    """
    known = by_name()
    text = hint(name)
    ghosts = []
    for clause in re.findall(
        r"(?:combine with|pair with|use with|alongside|together with)\s+([^.;]{0,120})", text, re.I
    ):
        for tok in re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", clause):
            # shorthand: hints write num_floors for primary_building_num_floors
            if tok in known or any(k.endswith("_" + tok) for k in known):
                continue
            if tok not in ghosts:
                ghosts.append(tok)
    return ghosts
