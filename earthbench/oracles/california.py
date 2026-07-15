"""California state hazard layers, emitted in Mireye's own field envelope.

Mireye's /v1/fetch returns each field as:

    {"value", "unit", "source", "source_url", "confidence",
     "fetched_at", "dataset_vintage", "ttl_seconds", "notes", "status"}

These five fields use the same contract, so they drop straight into a Mireye
response. Mireye carries no state sources (their FAQ: "Every data source we use
is federal"), which is why none of this exists in their 255-field catalog.

Field                              Why it matters
---------------------------------  ------------------------------------------
calfire_fhsz_class                 The map California insurers actually
                                   underwrite on. Reclassification into a
                                   higher tier is the #1 driver of non-renewal.
calfire_fhsz_responsibility_area    LRA vs SRA. Determines who sets the zone
                                   and which defensible-space rules apply.
cgs_liquefaction_zone              Legally-mandated disclosure (Civil Code 1103)
cgs_landslide_zone                 Legally-mandated disclosure
cgs_alquist_priolo_fault_zone      Legally-mandated disclosure

A NOTE ON NULL. The CGS publishes an "Unevaluated Areas" layer: large parts of
California have simply never been mapped for seismic hazard. So a point that is
not inside a liquefaction polygon is either genuinely outside the zone OR in an
area nobody has assessed. Those are completely different facts and collapsing
them into `false` is how you get an agent confidently telling a homeowner their
house is fine. We return None with status="unevaluated" instead.
"""

import datetime as _dt

from .arcgis import LayerUnavailable, query_point

CALFIRE_LRA = "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSALRA25_v1_All/FeatureServer/0"
CALFIRE_SRA = "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSZSRA_23_3/FeatureServer/0"

CGS_LIQUEFACTION = "https://services2.arcgis.com/zr3KAIbsRSUyARHG/ArcGIS/rest/services/CGS_Liquefaction_Zones/FeatureServer/0"
CGS_LANDSLIDE = "https://services2.arcgis.com/zr3KAIbsRSUyARHG/ArcGIS/rest/services/CGS_Landslide_Zones/FeatureServer/0"
CGS_ALQUIST_PRIOLO = "https://services2.arcgis.com/zr3KAIbsRSUyARHG/ArcGIS/rest/services/CGS_Alquist_Priolo_Fault_Zones/FeatureServer/0"
CGS_UNEVALUATED = "https://services2.arcgis.com/zr3KAIbsRSUyARHG/ArcGIS/rest/services/CGS_SHZ_Unevaluated_Areas/FeatureServer/0"

CALFIRE_PORTAL = "https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones"
CGS_PORTAL = "https://www.conservation.ca.gov/cgs/geohazards/regulatory-maps"

_DAY = 86_400


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _envelope(value, *, unit, source, source_url, confidence, vintage, ttl, notes, status="ok"):
    return {
        "value": value,
        "unit": unit,
        "source": source,
        "source_url": source_url,
        "confidence": confidence,
        "fetched_at": _now(),
        "dataset_vintage": vintage,
        "ttl_seconds": ttl,
        "notes": notes,
        "status": status,
    }


def _unavailable(source, source_url, exc):
    return _envelope(
        None, unit=None, source=source, source_url=source_url,
        confidence="low", vintage=None, ttl=0,
        notes=f"upstream service unavailable: {exc}", status="error",
    )


def fetch_fhsz(lat: float, lng: float) -> dict:
    """CAL FIRE Fire Hazard Severity Zone.

    A parcel sits in either a Local Responsibility Area or a State
    Responsibility Area, never both, so we query each and take whichever hits.
    """
    for area, url, vintage in (
        ("LRA", CALFIRE_LRA, "CAL FIRE FHSZ Local Responsibility Area, 2025 update"),
        ("SRA", CALFIRE_SRA, "CAL FIRE FHSZ State Responsibility Area, 2023 (23_3)"),
    ):
        try:
            hits = query_point(url, lat, lng)
        except LayerUnavailable as exc:
            return {
                "calfire_fhsz_class": _unavailable("CALFIRE_FHSZ", CALFIRE_PORTAL, exc),
                "calfire_fhsz_responsibility_area": _unavailable("CALFIRE_FHSZ", CALFIRE_PORTAL, exc),
            }
        if hits:
            attrs = hits[0]
            klass = attrs.get("FHSZ_Description")
            return {
                "calfire_fhsz_class": _envelope(
                    klass, unit=None, source="CALFIRE_FHSZ", source_url=CALFIRE_PORTAL,
                    confidence="high", vintage=vintage, ttl=180 * _DAY,
                    notes=(
                        f"parcel-mapped fire hazard severity zone ({area}); "
                        "this is the map California insurers underwrite on and the "
                        "trigger for wildfire non-renewal"
                    ),
                ),
                "calfire_fhsz_responsibility_area": _envelope(
                    area, unit=None, source="CALFIRE_FHSZ", source_url=CALFIRE_PORTAL,
                    confidence="high", vintage=vintage, ttl=180 * _DAY,
                    notes="LRA zones are set by CAL FIRE and adopted locally; SRA zones are state-enforced",
                ),
            }

    # Outside both -- e.g. federal land, which has no state zone at all.
    return {
        "calfire_fhsz_class": _envelope(
            None, unit=None, source="CALFIRE_FHSZ", source_url=CALFIRE_PORTAL,
            confidence="high", vintage="CAL FIRE FHSZ LRA 2025 + SRA 2023",
            ttl=180 * _DAY, status="not_zoned",
            notes="point falls outside both LRA and SRA zoning (typically Federal Responsibility Area)",
        ),
        "calfire_fhsz_responsibility_area": _envelope(
            None, unit=None, source="CALFIRE_FHSZ", source_url=CALFIRE_PORTAL,
            confidence="high", vintage="CAL FIRE FHSZ LRA 2025 + SRA 2023",
            ttl=180 * _DAY, status="not_zoned", notes="likely Federal Responsibility Area",
        ),
    }


def _fetch_cgs_zone(lat, lng, *, field, service_url, label, unevaluated: bool):
    """A CGS regulatory zone is boolean: you are inside the polygon or you aren't.

    But "not inside" only means "safe" if CGS actually evaluated the area, which
    is why `unevaluated` is passed in from a separate layer query.
    """
    try:
        hits = query_point(service_url, lat, lng)
    except LayerUnavailable as exc:
        return {field: _unavailable("CGS_SHZ", CGS_PORTAL, exc)}

    if hits:
        attrs = hits[0]
        # Each quad carries a link to the official CGS report -- a real citation.
        citation = attrs.get("REPORTLINK") or attrs.get("GEOPDFLINK") or CGS_PORTAL
        quad = attrs.get("QUAD_NAME")
        return {
            field: _envelope(
                True, unit=None, source="CGS_SHZ", source_url=citation,
                confidence="high",
                vintage=f"CGS Seismic Hazards Program, {quad} quadrangle",
                ttl=365 * _DAY,
                notes=(
                    f"inside a state-designated {label} zone; this is a mandatory "
                    "disclosure on any California property sale (Civil Code 1103)"
                ),
            )
        }

    if unevaluated:
        return {
            field: _envelope(
                None, unit=None, source="CGS_SHZ", source_url=CGS_PORTAL,
                confidence="low", vintage="CGS SHZ Unevaluated Areas",
                ttl=365 * _DAY, status="unevaluated",
                notes=(
                    f"CGS has never mapped this area for {label}. This is NOT the "
                    "same as being outside the zone -- the hazard is unknown, not absent."
                ),
            )
        }

    return {
        field: _envelope(
            False, unit=None, source="CGS_SHZ", source_url=CGS_PORTAL,
            confidence="high", vintage="CGS Seismic Hazards Program",
            ttl=365 * _DAY,
            notes=f"CGS evaluated this area and it lies outside the {label} zone",
        )
    }


def fetch_ca_layers(lat: float, lng: float) -> dict:
    """All five California state hazard fields, in Mireye's field envelope."""
    fields = {}
    fields.update(fetch_fhsz(lat, lng))

    try:
        unevaluated = bool(query_point(CGS_UNEVALUATED, lat, lng))
    except LayerUnavailable:
        # If we can't tell whether CGS evaluated the area, we must not claim it did.
        unevaluated = True

    for field, url, label in (
        ("cgs_liquefaction_zone", CGS_LIQUEFACTION, "liquefaction"),
        ("cgs_landslide_zone", CGS_LANDSLIDE, "earthquake-induced landslide"),
        ("cgs_alquist_priolo_fault_zone", CGS_ALQUIST_PRIOLO, "Alquist-Priolo earthquake fault"),
    ):
        fields.update(
            _fetch_cgs_zone(lat, lng, field=field, service_url=url, label=label, unevaluated=unevaluated)
        )

    return fields
