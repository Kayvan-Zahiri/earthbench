"""The agent: plan, gather, guard, rank, explain.

It answers "which of these parcels would you write, and why" for wildfire
underwriting. The interesting part is not the ranking, it is that the agent
refuses to rank on hazard when hazard cannot be grounded, and says so.

Pipeline:

  plan     read the catalog's preset and interpretation_hints rather than
           guessing field names. The benchmark measured a guessing agent at
           21/39 wrong names.
  gather   one /v1/fetch/batch call for every candidate. Before this endpoint
           existed, holding candidates side by side took N round trips.
  guard    hazard.assess. Never converts fuel proxies into a hazard verdict.
  request  when the decisive field is absent from the catalog, file a
           /v1/field-requests for it instead of substituting a proxy.
  rank     order on the grounded rating, break ties on documented thresholds.
  explain  every number carries its source, and each site says what would
           change its answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import catalog, client, hazard


@dataclass
class Site:
    name: str
    lat: float
    lng: float


@dataclass
class SiteResult:
    site: Site
    fields: dict = field(default_factory=dict)
    verdict: hazard.Verdict | None = None
    flags: list[str] = field(default_factory=list)
    would_change: list[str] = field(default_factory=list)


@dataclass
class Report:
    use_case: str
    planned_fields: list[str]
    missing_decisive: list[str]
    ghost_hints: dict[str, list[str]]
    results: list[SiteResult]
    field_request: dict | None = None


#: Names an agent would reach for to ground a wildfire hazard call. The
#: benchmark's tool-choice run watched a real agent invent these unprompted.
DECISIVE_WILDFIRE = ("fire_hazard_severity_zone", "burn_probability", "wildfire_risk_to_homes")


def plan(use_case: str = "wildfire_underwrite") -> tuple[list[str], list[str], dict]:
    """Pick fields from the catalog. Report what is missing and what hints lie."""
    fields = catalog.preset(use_case)
    missing = [n for n in DECISIVE_WILDFIRE if not catalog.exists(n)]
    ghosts = {n: g for n in fields if (g := catalog.ghost_references(n))}
    return fields, missing, ghosts


def gather(sites: list[Site], fields: list[str]) -> dict[int, dict]:
    locations = [{"lat": s.lat, "lng": s.lng} for s in sites]
    out: dict[int, dict] = {}
    for chunk_start in range(0, len(locations), 25):
        chunk = locations[chunk_start : chunk_start + 25]
        for r in client.fetch_batch(chunk, fields):
            if r.get("ok"):
                out[chunk_start + r["index"]] = r.get("fields", {})
    return out


def _threshold_flags(fields: dict) -> list[str]:
    """Apply the numeric cutoffs Mireye states in its own hints."""
    flags = []
    for name in ("slope_degrees",):
        v = fields.get(name)
        v = v.get("value") if isinstance(v, dict) else v
        if v is None:
            continue
        for t in catalog.thresholds(name):
            if t["op"] == ">" and v > t["value"]:
                flags.append(f"{name} {v:.1f}{t['unit']} exceeds {t['value']:g}{t['unit']}: {t['means']}")
    return flags


def file_field_request(sites: list[Site], missing: list[str]) -> dict | None:
    """Ask Mireye to build the hazard field rather than proxy around it."""
    if not missing:
        return None
    examples = [{"lat": s.lat, "lng": s.lng, "note": s.name} for s in sites[:10]]
    payload = dict(
        description=(
            "Regulatory wildfire hazard severity class for a US coordinate, as "
            "published by the authority that sets it (CAL FIRE FHSZ in California, "
            "equivalent state or federal rating elsewhere). The catalog currently "
            "carries fuel and terrain proxies only (tree_canopy_pct, ndvi_current, "
            "lcms_class, slope_degrees), which cannot separate land that never "
            "carried fuel from land that burned. At Paradise CA the wildfire_underwrite "
            "preset returns canopy 1.0% and NDVI 0.109 while CAL FIRE rates the same "
            "point Very High."
        ),
        example_locations=examples,
        use_case=(
            "Wildfire underwriting and siting. An agent ranking candidate parcels "
            "needs the rating the insurer prices against, not a proxy for it."
        ),
        decision_threshold=(
            "Very High or High typically changes admitted-market appetite and can "
            "route a risk to surplus lines, so the class itself is the decision."
        ),
        # NOTE: suggested/excluded take objects, not strings. Passing strings
        # returns 422 invalid_payload with a per-item pointer, which is a good
        # error but the docs' field table does not show the item shape.
        known_sources={
            "suggested": [
                {
                    "name": "CAL FIRE OSFM Fire Hazard Severity Zones (LRA 2025, SRA 2023)",
                    "url": "https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones",
                },
                {
                    "name": "USFS Wildfire Risk to Communities",
                    "url": "https://wildfirerisk.org/",
                },
            ]
        },
        idempotency_key="earthbench-agent-wildfire-hazard-class-v1",
    )
    try:
        return {"status": "filed", "response": client.request_field(**payload)}
    except client.MireyeError as exc:
        # Free plan reports field_requests_included: 0. Record the ask anyway:
        # the gap and the request are the finding, not the HTTP status.
        return {
            "status": "not_filed",
            "http_status": exc.status,
            "error": exc.body,
            "payload_would_send": payload,
        }


def run(sites: list[Site], *, use_case: str = "wildfire_underwrite", authoritative=hazard.calfire) -> Report:
    planned, missing, ghosts = plan(use_case)
    gathered = gather(sites, planned)

    results = []
    for i, s in enumerate(sites):
        f = gathered.get(i, {})
        v = hazard.assess(s.lat, s.lng, f, authoritative=authoritative)
        flags = _threshold_flags(f) + list(v.warnings)
        change = []
        if not v.decided:
            change.append("a regulatory hazard rating for this coordinate")
        if any("burn scar" in w for w in v.warnings):
            change.append("fire perimeter history, to tell a burn scar from pavement")
        results.append(SiteResult(site=s, fields=f, verdict=v, flags=flags, would_change=change))

    order = {"Very High": 0, "High": 1, "Moderate": 2, "Low": 3}
    results.sort(key=lambda r: (not r.verdict.decided, order.get(r.verdict.rating, 9), r.site.name))

    return Report(
        use_case=use_case,
        planned_fields=planned,
        missing_decisive=missing,
        ghost_hints=ghosts,
        results=results,
        field_request=file_field_request(sites, missing),
    )
