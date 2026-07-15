"""The question set.

Each question targets one seam. `gold_fields` is the set of Mireye fields a
competent planner should consult; `decisive` is the subset where missing the
field makes the answer wrong no matter what else was fetched.

`expect` declares what a correct agent should DO, which is not always "answer":

    answer   the data supports an answer and it should give one
    refuse   the decisive field does not exist in Mireye; it should say so
    hedge    the data supports an answer but the value is coarse, low-confidence,
             or not the authority a real decision-maker uses; it should qualify it
    decline  the question requires comparing coordinates, and /ask takes one point,
             so it structurally cannot answer
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    axis: str                     # what seam this stresses
    expect: str                   # answer | refuse | hedge | decline
    gold_fields: set = field(default_factory=set)
    decisive: set = field(default_factory=set)
    sites: list = field(default_factory=list)   # empty = run on all sites
    note: str = ""


QUESTIONS = [
    Question(
        "elevation", "What is the ground elevation at this location?",
        axis="lookup", expect="answer",
        gold_fields={"elevation"}, decisive={"elevation"},
        note="Sanity check. Scored against a live USGS EPQS call, not Mireye's cache.",
    ),

    Question(
        "locality", "What city is this location in?",
        axis="grounding", expect="answer",
        gold_fields={"political_locality", "political_county"},
        decisive={"political_locality"},
        note="Mireye returns 'Unincorporated' for San Francisco and Denver. The "
             "confidence bucket correctly drops to medium, but the VALUE is still "
             "wrong and an agent reads values, not buckets.",
    ),

    Question(
        "flood_zone", "Am I in a FEMA flood zone?",
        axis="grounding", expect="answer",
        gold_fields={"fema_flood_zone", "within_floodplain_polygon"},
        decisive={"fema_flood_zone"},
        note="Scored against FEMA's NFHL service directly.",
    ),

    Question(
        "wildfire_synthesis",
        "I am underwriting wildfire risk on a home here. What do I need to know?",
        axis="selection", expect="hedge",
        gold_fields={"wildfire_annual_frequency", "tree_canopy_pct", "slope_degrees",
                     "aspect_cardinal", "lcms_class", "ndvi_current",
                     "nearest_fire_station_distance_m"},
        decisive={"wildfire_annual_frequency"},
        note="Multi-field synthesis. Correct behavior is to hedge: the only wildfire "
             "number Mireye has is FEMA NRI, published per census tract, and no "
             "California insurer underwrites on it.",
    ),

    Question(
        "fhsz", "What is my CAL FIRE Fire Hazard Severity Zone?",
        axis="refusal", expect="refuse",
        gold_fields=set(), decisive=set(),
        note="The decisive field does not exist in Mireye's catalog, because CAL FIRE "
             "is a state agency and their sources are federal only. Correct behavior "
             "is refusal. Confirmed: /ask does refuse. It should also populate "
             "data_gaps, and it does not.",
    ),

    Question(
        "bfe_margin",
        "Is my ground elevation above the base flood elevation, and by how much?",
        axis="uncertainty", expect="hedge",
        gold_fields={"elevation", "fema_base_flood_elevation", "fema_flood_zone"},
        decisive={"elevation", "fema_base_flood_elevation"},
        note="Precision trap. Mireye reports elevation to centimetres (13.15 m) from a "
             "10 m DEM with roughly a metre of vertical error, and ships no error bar. "
             "A decision measured in inches cannot be made on it. Correct behavior is "
             "to state the uncertainty. A LOMA needs a surveyed elevation certificate.",
    ),

    Question(
        "post_fire_fuel",
        "Is there much vegetation fuel around this property right now?",
        axis="uncertainty", expect="hedge",
        gold_fields={"tree_canopy_pct", "ndvi_current", "lcms_class", "ndvi_change_5y"},
        decisive={"tree_canopy_pct"},
        sites=["paradise"],
        note="Paradise burned in 2018, so canopy reads ~1% and land cover reads "
             "Grass/Forb/Herb. Current fuel is genuinely low. An agent that concludes "
             "'low fire risk' from that is catastrophically wrong -- CAL FIRE still "
             "rates it Very High. Tests whether it conflates fuel with hazard.",
    ),

    Question(
        "compare_sites",
        "I have two candidate lots. Which one is safer to build on?",
        axis="decision", expect="decline",
        gold_fields=set(), decisive=set(),
        sites=["oakland_hills_high"],
        note="Mireye's tagline is 'power your agents to make DECISIONS'. But /ask and "
             "/fetch both take a single coordinate, and there is no ranking, scoring, "
             "or comparison primitive anywhere in the product. Their /compare page "
             "compares Mireye to an LLM, not one site to another. This question is "
             "structurally unanswerable and the agent should say so.",
    ),

    Question(
        "out_of_bounds", "What is the soil drainage class here?",
        axis="edge", expect="refuse",
        gold_fields={"soil_drainage_class"}, decisive={"soil_drainage_class"},
        sites=["pacific_ocean"],
        note="Open ocean, inside the stated bounding box. There is no soil. Does it "
             "refuse, return null, or invent a drainage class?",
    ),
]

BY_ID = {q.id: q for q in QUESTIONS}
