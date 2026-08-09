# Audit log

Every claim this project makes, and what happened when it was checked.

This exists because the benchmark is worthless if its own numbers cannot survive
the scrutiny it applies to Mireye. Three of the findings below were retracted
after checking. Two of them were the benchmark's fault, not Mireye's.

---

## Verified: safe to state

**1. Mireye carries no California state hazard layers.**
Grepped all 255 fields in the live catalog (`api.mireye.com/v1/meta/fields`, v0.14.0).
No CAL FIRE Fire Hazard Severity Zone. No CGS liquefaction, landslide, or
Alquist-Priolo. Their FAQ says why, in their own words: *"Every data source we use
is federal."* Exactly one state source exists in the entire product
(`CARB_AIR_DISTRICTS`, powering one field).

**2. Their only wildfire field answers a different question than the one asked.**
At Paradise CA (2018 Camp Fire, 85 dead), `wildfire_annual_frequency` = **0.00847**
events/year, sourced from FEMA NRI, `confidence: medium`, and the field's own notes
say it is the value for **census tract** 06007000900. CAL FIRE rates that parcel
**Very High**. No California insurer underwrites on FEMA NRI.

**3. The resolution gap is irrecoverable, not merely missing.**
Census tract **06001404400** contains parcels CAL FIRE rates **High** and parcels it
rates **NonWildland**. FEMA NRI is published per tract, so Mireye returns the
identical number (0.001982) to both. No post-processing of Mireye's data can
recover the distinction, because the information is not in it.
*Scope note: this is an existence proof, from a 15-point transect. One collision is
sufficient to prove non-recoverability. Do not quote "2 of 7 tracts" as a rate: the
transect was not designed to measure prevalence.*

**4. `political_locality` fails for county-equivalent cities.**
16/16 sampled points inside San Francisco County return `"Unincorporated"`.
Across 28 major US cities, 4 fail: **San Francisco, Denver, Baltimore, St. Louis**
(~2.4M residents). All four are cities that are their own county-equivalent
(two consolidated city-counties, two independent cities). The other 24 resolve
correctly.
*Honest limits: the field mostly works, 24/28. And the mechanism is narrower than
"consolidated city-counties," because Philadelphia, Nashville, New Orleans, Honolulu
and Indianapolis are also consolidated or coextensive and resolve fine. Root cause
inside Overture's division hierarchy was not chased. Say so.*

**5. A raw LLM with no data beats Mireye on that question.**
Opus 4.8, no tools, no lookups: `"San Francisco"` 5/5 trials at high confidence;
`"Denver"` 5/5 at high confidence. Mireye returns `"Unincorporated"`, with a
federal citation attached. The citation makes the wrong answer *more* credible than
the right guess.

**6. Mireye's moat is real, and the same table proves it.**
Same model, same conditions, asked for elevation at the SF Marina: **100 m**
(true value 7.5 m, it confused the Marina with Pacific Heights). Mireye: **7.53 m**.
Asked for a FEMA flood zone, the model refuses outright. Over the full run Mireye
wins 17 head-to-heads and loses 3.

**7. `/ask` is non-deterministic, and it matters most where it matters most.**
Identical question, identical coordinate, k=4 calls. 3 of 6 cases returned
**different field sets**. Prose differed on every call.

| case | distinct field sets / 4 | jaccard |
|---|---|---|
| `elevation @ sf_marina` | 1 | 1.00 |
| `flood_zone @ guerneville` | 1 | 1.00 |
| `fhsz @ oakland_hills_high` (refusal) | 1 | 1.00 |
| `locality @ sf_marina` | 2 | 0.33 |
| `post_fire_fuel @ paradise` | 3 | 0.67 |
| `wildfire_synthesis @ oakland_hills_high` | 3 | 0.64 |

Single-field lookups are perfectly stable. **Multi-field synthesis is not**: the
compound questions a real agent actually asks. On one wildfire underwriting query,
separate calls pulled `nearest_fire_station_distance_m`, then
`primary_building_footprint_sqm` + `primary_building_height_m` +
`nearest_major_road_distance_m`, then neither.

Their product is sold as **audit-ready**. An audit trail that does not reproduce is
not an audit trail.

**8. `data_gaps` reports missing *values*, not missing *coverage*.**
It populates correctly when a source returns null (verified on flood zone, BFE, and
an out-of-bounds ocean coordinate). It populated **0/12** times on the CAL FIRE
question, a real coverage gap. An agent has no programmatic way to learn that an
entire dataset is absent.

**9. Elevation is reported to a precision its source cannot support.**
USGS 3DEP 1/3 arc-second seamless DEM: **0.82 m RMSE** across CONUS as of 2022,
measured against ~25,000 NOAA NGS OPUS points, and varying substantially by
location ([USGS](https://www.usgs.gov/faqs/what-vertical-accuracy-3d-elevation-program-3dep-dems)).
Mireye reports elevation to the centimetre: their own homepage prints
`13.15 meters`, with **no error bar anywhere in the field envelope.**

**10. There is no decision primitive.**
`/ask` and `/fetch` both take a single coordinate. No ranking, scoring,
thresholding, or comparison exists anywhere in the product. Their page named
"Compare" compares *Mireye against an LLM*, not one site against another. Asked to
compare two lots, `/ask` refuses, but with the *wrong reason*: it reports the
question as unanswerable from its datasets, when the datasets are fine and the
limitation is the API shape. A misdiagnosed refusal teaches an agent the wrong
lesson.

**11. The MCP funnels agents into the product's worst failure mode.**
Tool descriptions taken verbatim from `mireye_earth_mcp` 0.1.0, rewriting them
would have measured the rewriter's prompt engineering, not Mireye's MCP.

- `mireye_fetch` takes field names out of a **255-field catalogue, and the MCP
  exposes no way to discover them.** `/v1/meta/fields` exists, is public, needs no
  token, and is not wired in. So the agent guesses.
- **54% of the field names it requests are not real fields** (21 of 39).
- Those split cleanly into two classes:
  - **7 name failures**: the field exists, the guess was near: `slope` for
    `slope_degrees`, `flood_zone` for `fema_flood_zone`, `ground_elevation` for
    `elevation`. **One new MCP tool closes all of these.**
  - **8 coverage failures**: no such field exists anywhere. Asked to underwrite
    wildfire, the agent reached unprompted for `fire_hazard_severity_zone`,
    `burn_probability`, `fire_history`, `wildland_urban_interface`. **It found the
    CAL FIRE gap by trying to do the job**, independently of finding #1, which came
    from reading the catalogue.
- Because `fetch` is unusable, the agent falls back on `ask`: it **over-asked on
  5 of 8** single-field lookups (every `locality` and `flood_zone` case).
- And `ask` is exactly where the synthesis layer escalates a `medium`-confidence
  `"Unincorporated"` into the flat assertion *"It does not lie within an
  incorporated city"* plus an invented *"near the Presidio."*

So findings #4, #7 and #11 are not three problems. They are one chain: no discovery
tool → field-name guessing → forced fallback to `ask` → error amplification.

---

## Retracted: claimed, then disproved by checking

**R1. "Systematic planner miss: `fema_base_flood_elevation` missed at 12/12 sites."**
**False, and it was the benchmark's fault.** `fields_used` only lists fields that
*returned a value*. A field the planner requested that came back null is reported in
`data_gaps` instead. The planner **did** request the BFE. FEMA simply has no static
NAVD88 BFE on that polygon.

Worse for the original claim: Mireye's answer at Guerneville (Zone AE) is the best
in the entire run. It explains that riverine AE zones encode BFE in a separate flood
profile line layer rather than the area polygon, states plainly that it **cannot**
compute a freeboard margin, drops to `confidence: low`, and directs the user to a
licensed floodplain manager or a formal Elevation Certificate. On the hardest,
most precision-sensitive question in the benchmark, designed as a trap, Mireye
passed. `checks/selection.py` was fixed to count fields attempted-but-null.

**R2. "`data_gaps` is never populated."**
**False.** It populates for null values. The true, narrower finding is #8 above.

**R3. "USGS 3DEP has ~1 m vertical RMSE."**
**Imprecise.** The figure is 0.82 m (2022). Asserted from memory, then checked.

---

## Benchmark bugs found by auditing the benchmark

1. Numeric faithfulness counted the echoed input coordinates and the `88` in
   "NAVD88" as unsupported claims, scoring 0.2 on a perfectly faithful answer.
   Fixed by excluding numbers that appear in the question or inside a cited field's
   own provenance metadata.
2. Selection scored off `fields_used` alone, punishing the planner for missing
   *data*. Fixed (see R1). **This bug was slandering the system under test.**
3. Selection penalized correct refusals with `decisive_recall = 0.0`. Fixed.
4. The whole harness ran one sample per pair, which is invalid given finding #7. Now
   samples k=3 and reports the spread.
5. `DEM_VERTICAL_RMSE_M` was hardcoded from memory. Now cited.

---

## What the benchmark does not measure

*(Kayvan to write. Candidates: N is small and the sites are California-weighted;
the LLM judge is validated against ~15 hand labels, not a large set; the head-to-head
uses one baseline model on one day; latency was not controlled for; no MCP tool-choice
layer was tested, only the /ask planner; sample-0 is used for detailed scoring even
though the endpoint is nondeterministic.)*
