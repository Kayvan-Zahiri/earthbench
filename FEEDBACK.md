# Feedback for Mireye

Everything here was verified live against the API on 2026-08-05, not taken
from the docs. Where a figure is older than that, it says so.

---

First, the part that is easy to lose in a list of complaints: **Mireye works.**
Across 75 (question, site) pairs it returned **zero false answers**, hedged on
25/25 of the questions where it should have, and held decisive-field recall on
`/ask` at 1.000, all re-confirmed on 2026-08-05. `fema_flood_zone` is 58/58
correct against live FEMA. It also beat a no-data LLM 19-3 in July, though that
comparison was not re-run. When it does not know, it usually says so.
Everything below is about the edges.

**1. `wildfire_underwrite` is six fuel proxies and no hazard rating, and it
inverts the order it is meant to rank.** The preset returns `elevation`,
`slope_degrees`, `lcms_class`, `tree_canopy_pct`, `ndvi_current`,
`ndvi_change_5y`. Paradise, CA scores canopy 1%, NDVI 0.11, "Grass/Forb/Herb",
which reads as low fuel. Paradise burned in 2018 and CAL FIRE rates it Very High.
Across eight sites the canopy ranges for Very High and NonWildland **overlap**,
and two NonWildland sites carry more canopy than the least-treed Very High site.
The proxies are correct; used for ranking they are actively misleading. The
preset needs a hazard rating in it, or a warning that it is not one.

**2. A hint names a field that does not exist.** `slope_degrees` says *"Combine
with `lcms_class` and `dist_to_wui_m` for wildfire underwriting."* Nothing
matching wui / wildland / interface exists in the 283 fields. Distance to the
wildland-urban interface is the central variable in wildfire underwriting, so
the hint reads as a promise. Either ship it or drop it from the hint.

**3. No state-level hazard layers, which is where the legal weight sits.** There
is no `fire_hazard_severity_zone`, `burn_probability` or
`wildfire_risk_to_homes`. In California the maps that carry statutory force are
state-owned (CAL FIRE, CGS), so federal-only sourcing leaves a structural hole in
exactly the decisions people pay for. This is the single highest-value thing you
could add.

**4. `/ask` is non-deterministic on multi-field questions.** Identical question,
identical coordinate, different field selections across calls. Stable on
single-field lookups, unstable on the synthesis a real agent actually asks. For a
product sold as *audit-ready*, a decision that does not reproduce is the finding
I would fix first: an underwriter cannot file an answer they cannot regenerate.

**5. `political_locality` returns "Unincorporated" for county-equivalent cities,
and it has got worse since July.** San Francisco, Denver, Baltimore and St. Louis
all come back unincorporated. Re-measured 2026-08-05 it is **26/50 against 32/50
on 2026-07-13**, and Manhattan has newly changed from "New York" to "Manhattan".
A raw LLM with no data beats you on "what city is this?" purely because of this.

**6. The MCP server has no field-discovery tool, and agents pay for it.** With no
way to list the fields, an agent guessing names got **21 of 39 wrong (54%)**,
then fell back to `/ask`, where a shaky value gets restated with more confidence.
`/v1/meta/fields` already exists and is public. Exposing it as one more MCP tool
would close most of this. It is the cheapest fix on this list, and reading the
catalog first is exactly what my agent does by hand, though its 6 planned
fields are a smaller test than the 39 name uses the benchmark scored.

**7. Elevation is precise past what it can support.** Reported to the centimetre
with no error bar. Nine of eleven land sites agree with a live USGS query within
0.6 m, so accuracy is fine, but 3DEP's own RMSE is 0.82 m, and a centimetre with
no interval reads as exact when it is not.

**8. There is no decision primitive.** Nothing ranks, compares, or refuses.
`/fetch/batch` was the missing half and it shipped, which closes the comparison
gap. What is still absent is anything that says "these two parcels differ in a
way that matters" or "I cannot answer this." That gap is what I built into the
agent, and I think it is where the product goes next: the buyer is not paying for
the data, they are paying for a decision they can defend.

---

Three things I thought I had found and was wrong about, recorded because they
shaped the rest: `num_floors` and `footprint_sqm` are shorthand for
`primary_building_*`, not missing fields; `nearest_within_radius`,
`utility_sourced` and `ml_modeled` are enum values, not fields; and the
single-coordinate limitation I reported earlier is now closed by `/fetch/batch`.
