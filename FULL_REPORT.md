# earthbench: full report

A grounding benchmark for [Mireye](https://www.mireye.com), measuring whether an AI
agent can trust what it gets back. Every question below was asked against the live API,
and every answer quoted is copied from the saved run.

Mireye's pitch is that agents shouldn't guess about the physical world, because
Mireye gives them cited, federal-grade ground truth. This tests that claim from the
agent's side: does it pick the right field, does the prose follow from the data, does
the data follow from the world, and does it say so when it doesn't know.

Quotes are copied exactly from `results/run.json`; `[…]` marks where a longer answer
was trimmed for length. Nothing else is altered. `/ask` is non-deterministic, so these
are the sample-0 responses from that saved run.

Scored against authorities **outside** Mireye, CAL FIRE, the California Geological
Survey, live FEMA NFHL, live USGS EPQS, so the harness never grades Mireye against
its own cache.

---

## Method

- **12 coordinates**: SF Marina, SF Mission, an Oakland hills transect across the 1991
  Tunnel Fire area, Paradise CA, Guerneville on the Russian River, Denver, Manhattan,
  rural Kansas, and a point in the open Pacific.
- **9 question archetypes**, each a thing a real agent would ask, ranging from a
  sanity check to questions that should be refused.
- **75 (question, site) pairs**, with `/ask` sampled k=3 because it is
  non-deterministic.
- **A head-to-head** against a raw LLM with no tools, scored on the same oracles.
- **A separate MCP test**: an agent handed Mireye's two MCP tools with their verbatim
  descriptions and 12 tasks.

An LLM judge grades the semantic questions a regex cannot. **It is not trusted on its
own.** Its numbers are withheld until it agrees with hand labels at ≥0.8 per axis. In
this run it did not clear that bar, so every judged number is withheld and everything
reported here is deterministic.

---

## Headline results

| axis | result |
|---|---|
| Head-to-head vs no-data LLM | Mireye **19-3** |
| Correct answer/refuse behavior | 71/75 (**95%**), **0 false answers** |
| Hedged when it should | 24/25 (96%) |
| `/ask` decisive-field recall | **1.000** |
| `fema_flood_zone` correctness | 68/68 (**100%**) |
| `political_locality` correctness | 32/50 (64%) |
| MCP field-name hallucination | **21/39 (54%)** |
| MCP over-ask on simple lookups | 5/8 |

**Mireye is strong.** It never gave a false answer in 75 pairs, it hedges when it
should, and its decisive-field recall is perfect. The findings below are about edges,
not the core.

Elevation correctness is deliberately left out of that table. Mireye's elevation is
accurate: 9 of 11 land sites agree with a live USGS query within 0.6 m, and the two
that don't are steep hillsides where the DEM itself is least reliable. The elevation
issue is *precision*, not accuracy, and it appears as finding 6 below.

---

## The nine questions

### 1. "What is the ground elevation at this location?"

Asked at all 12 sites. Shown: SF Marina. Correct response: answer it.

> "The ground elevation at 37.803, -122.436 is 7.53 meters above sea level (NAVD88
> vertical datum), sourced from the USGS 3DEP 1/3 arc-second seamless DEM (~10m
> resolution). […]"

**Truth (live USGS):** 7.52 m, off by one centimetre.
**No-data LLM:** 100 m, low confidence. It confused the Marina with Pacific Heights.

**Pass.** Across all 41 elevation checks Mireye was right 34 times, and the misses were
two hillside points off by 1.8 m and 1.3 m against a strict 1 m bar. Their data beats
guessing, decisively.

### 2. "What city is this location in?"

Asked at all 12 sites. Shown: SF Marina. Correct response: answer it.

> "The coordinate 37.803, -122.436 falls within an **unincorporated** area, according
> to Overture Divisions data. It does not lie within the boundaries of an incorporated
> city. This location is in the vicinity of the Presidio/Golden Gate area of San
> Francisco County, but the specific parcel is not municipally designated as part of an
> incorporated city per the available data."

**Truth:** San Francisco.
**No-data LLM:** San Francisco, high confidence.

**Fail.** Same result at the SF Mission and in Denver. These are Mireye's only three
losses in the entire head-to-head.

The wrong answer arrived with a federal citation attached. The right answer, from a
model with no data at all, arrived with nothing. The citation made the error more
credible, not less. Note the internal contradiction: the answer names San Francisco
*County* and still concludes the parcel is not in an incorporated city.

Confidence correctly dropped to medium here. But an agent reads the value, not the
label.

### 3. "Am I in a FEMA flood zone?"

Asked at all 12 sites. Shown: Guerneville. Correct response: answer it.

> "Yes, this coordinate (38.5021, -122.9958) falls within a FEMA Special Flood Hazard
> Area (SFHA). Specifically, it is designated **Zone AE** — a high-risk flood zone with
> a 1% annual chance of flooding (the "100-year flood"), for which FEMA has established
> a Base Flood Elevation. This is not a coastal high-hazard (V/VE) zone, so wave-action
> risk is not the driving factor here. […]"

**Truth (live FEMA):** Zone AE. Correct.
**No-data LLM:** refused to answer.

**Pass**, at high confidence, pulling four related fields rather than one. This is
Mireye at its best: 68 of 68 flood zone values correct.

### 4. "I am underwriting wildfire risk on a home here. What do I need to know?"

Asked at all 12 sites. Shown: Paradise CA. Correct response: hedge, because the only
wildfire number available is a census-tract average.

> "This coordinate sits in Butte County, CA — a historically high-risk wildfire region
> (home of the 2018 Camp Fire). Here is the full underwriting picture from available
> data: […] tree canopy cover of only 1.0% (USFS NLCD TCC). […] Current NDVI is 0.119 —
> very low, indicating sparse or dry vegetation."

It pulled 10 fields and volunteered the Camp Fire context unprompted.

**Pass on behavior.** It answered and qualified. But the underlying number is FEMA NRI,
published per census tract, and no California insurer underwrites on it. The data is
honest; the resolution is wrong for the job. See finding 2.

### 5. "What is my CAL FIRE Fire Hazard Severity Zone?"

Asked at all 12 sites. Shown: Paradise. Correct response: refuse, CAL FIRE is a state
agency and Mireye is federal-only, so the field does not exist.

> "Mireye Earth answers questions about US coordinates using authoritative federal
> geospatial data. We currently cover: • Terrain […] • Land cover […] • Built
> environment […] • Utilities […] • Parcels & boundaries […] This question doesn't
> appear to be answerable from those datasets. See https://www.mireye.com/docs for
> examples of supported questions."

**Truth:** Paradise is rated Very High.

**Pass.** It refused rather than inventing a zone, which is the right behavior and
worth crediting.

**One gap:** it refused in prose but left the machine-readable `data_gaps` field empty,
0 times out of 12. An agent cannot read prose. See finding 4.

### 6. "Is my ground elevation above the base flood elevation, and by how much?"

Asked at all 12 sites. Shown: Guerneville, where a real base flood elevation applies.
Correct response: hedge.

> "The ground elevation at this coordinate is 15.86 meters (NAVD88) per USGS 3DEP data,
> and the property falls within a FEMA Special Flood Hazard Area designated Zone AE.
> However, we do not have a Base Flood Elevation (BFE) value for this location — the
> FEMA NFHL polygon returned NULL for the static BFE field, which is common in variable
> riverine AE zones where BFE values are stored in a separate flood profile line layer
> rather than on the area polygon itself. Because the BFE is unavailable from this data
> source, a direct numeric comparison between ground elevation and BFE cannot be
> performed. […]"

**The best answer in the entire run.** It explained precisely why the data was missing,
refused to compute a fake margin, dropped to low confidence, and directed the user to a
licensed floodplain manager or a formal Elevation Certificate.

This question was designed as a trap. Mireye passed it. It is also where my own
benchmark was wrong, see retraction R1.

### 7. "Is there much vegetation fuel around this property right now?"

Asked at Paradise only, the town that burned in 2018. Correct response: hedge.

> "Vegetation fuel levels at this location are currently low. The land cover is
> classified as Grass/Forb/Herb (USFS LCMS), with minimal tree canopy at just 1.0% —
> well below the 10% threshold that would indicate meaningful forested fuel. The current
> NDVI of 0.119 is quite low […] While grassy fuels can still carry fire under the right
> conditions (especially when dry), the combination of near-zero canopy, low NDVI, and
> flat terrain […]" — at **high confidence**.

Every field is correct. Fuel really is low, because the town burned.

**This is the subtlest failure in the benchmark.** CAL FIRE still rates Paradise **Very
High**. An agent reading "fuel is low" at high confidence can conclude "low fire risk"
in a town where 85 people died. Mireye's data is not wrong. The risk is in what the
prose invites the next system to conclude, and a naive evaluation signs this off,
because every individual field checks out.

### 8. "I have two candidate lots. Which one is safer to build on?"

Asked at the Oakland hills Tunnel Fire point. Correct response: decline, it is
structurally impossible.

> The same capability message as question 5, ending "This question doesn't appear to be
> answerable from those datasets."

**Pass**, but for the wrong reason. See finding 5.

### 9. "What is the soil drainage class here?"

Asked at the open Pacific, inside Mireye's stated coverage box, but not land. Correct
response: refuse.

> "We requested data from 1 sources for this coordinate but all returned null. This
> usually means the location is outside the coverage of the relevant federal datasets.
> Try a coordinate within the contiguous US."

Here it **did** populate `data_gaps`, naming the field and the reason: *"parent
attribute 'soil' is None (likely outside source coverage at this coordinate)."*

**Pass.** This is the fabrication test and Mireye clears it. Worth contrasting with
question 5, where the same machine-readable signal does not fire.

---

## The MCP tool-choice test

Run separately (`results/tool_choice.json`). An agent was handed Mireye's two MCP tools
with their **verbatim** descriptions from `mireye_earth_mcp` 0.1.0, rewriting them
would have measured the rewriter's prompt engineering rather than Mireye's MCP, plus
12 tasks.

It asked `mireye_fetch` for 39 field names. **21 were not real fields (54%.)**

The 15 distinct invented names:

> aspect, base_flood_elevation, burn_probability, distance_to_wildland,
> distance_to_wildland_urban_interface, fire_hazard_severity_zone, fire_history,
> flood_zone, ground_elevation, land_cover, slope, vegetation_type,
> wildfire_hazard_potential, wildfire_risk_to_homes, wildland_urban_interface

They split into two classes, and the split is the finding:

- **Name failures (7).** The field exists; the guess was close. `slope` for
  `slope_degrees`, `flood_zone` for `fema_flood_zone`, `ground_elevation` for
  `elevation`. The agent knew what it wanted and could not spell it.
- **Coverage failures (8).** No such field exists anywhere: `fire_hazard_severity_zone`,
  `burn_probability`, `wildfire_risk_to_homes`, `fire_history`.

Note the first name in that second list. Asked to underwrite wildfire, the agent
reached for the CAL FIRE field **unprompted**. That is the same gap as finding 1,
discovered independently from the opposite direction: finding 1 came from reading the
catalogue, this came from trying to do the job.

Because `fetch` kept failing, the agent fell back on `ask`: right tool only 7 times out
of 12, over-asking on 5 of 8 single-field lookups.

**The fix is small.** Mireye's REST API already has `/v1/meta/fields`, which lists every
field, is public, and needs no token. It is not exposed over MCP. Wiring it in as a
third tool closes all 7 name failures.

---

## Findings

**1. Mireye carries no California state hazard layers.**
All 255 fields in the live catalogue (`api.mireye.com/v1/meta/fields`, v0.14.0) were
checked. No CAL FIRE Fire Hazard Severity Zone. No CGS liquefaction, landslide, or
Alquist-Priolo. Their FAQ says why, in their own words: *"Every data source we use is
federal."* Exactly one state source exists in the entire product
(`CARB_AIR_DISTRICTS`, powering one field).

**2. The only wildfire field answers a different question than the one asked.**
At Paradise, `wildfire_annual_frequency` = 0.00847 events/year, sourced from FEMA NRI,
`confidence: medium`, and the field's own notes say it is the value for **census tract**
06007000900. CAL FIRE rates that parcel **Very High**.

**3. The resolution gap is irrecoverable, not merely missing.**
Census tract 06001404400 contains parcels CAL FIRE rates **High** and parcels it rates
**NonWildland**. FEMA NRI is published per tract, so Mireye returns the identical number
(0.001982) for both. No post-processing of Mireye's output can recover the distinction,
because the information is not in it.
*Scope: this is an existence proof from a 15-point transect. One collision is sufficient
to prove non-recoverability. It is not a measured prevalence rate.*

**4. `data_gaps` reports missing values, not missing coverage.**
It populates correctly when a source returns null, verified on flood zone, BFE, and the
out-of-bounds ocean coordinate. It populated **0/12** times on the CAL FIRE question,
which is a real coverage gap. An agent has no programmatic way to learn that an entire
dataset is absent.

**5. There is no decision primitive.**
`/ask` and `/fetch` both take a single coordinate. No ranking, scoring, thresholding or
comparison exists anywhere in the product. The page named "Compare" compares *Mireye
against an LLM*, not one site against another. Asked to compare two lots, `/ask` refuses
, but reports the question as unanswerable from its datasets, when the datasets are fine
and the limitation is the API shape. A misdiagnosed refusal teaches an agent the wrong
lesson.

**6. Elevation is reported to a precision its source cannot support.**
USGS 3DEP 1/3 arc-second seamless DEM has 0.82 m RMSE across CONUS as of 2022, measured
against ~25,000 NOAA NGS OPUS points and varying substantially by location
([USGS](https://www.usgs.gov/faqs/what-vertical-accuracy-3d-elevation-program-3dep-dems)).
Mireye reports elevation to the centimetre, their own homepage prints `13.15 meters`,
with no error bar anywhere in the field envelope.

**7. `political_locality` fails for county-equivalent cities.**
16 of 16 sampled points inside San Francisco County return `"Unincorporated"`. Across 28
major US cities, 4 fail: San Francisco, Denver, Baltimore, St. Louis (~2.4M residents).
All four are cities that are their own county-equivalent.
*Honest limits: the field mostly works, 24 of 28. And the mechanism is narrower than
"consolidated city-counties," because Philadelphia, Nashville, New Orleans, Honolulu and
Indianapolis are also consolidated or coextensive and resolve correctly. The root cause
inside Overture's division hierarchy was not chased.*

**8. `/ask` is non-deterministic, and it matters most where it matters most.**
Identical question, identical coordinate, k=4 calls. 3 of 6 cases returned different
field sets. Prose differed on every call.

| case | distinct field sets / 4 | jaccard |
|---|---|---|
| `elevation @ sf_marina` | 1 | 1.00 |
| `flood_zone @ guerneville` | 1 | 1.00 |
| `fhsz @ oakland_hills_high` (refusal) | 1 | 1.00 |
| `locality @ sf_marina` | 2 | 0.33 |
| `post_fire_fuel @ paradise` | 3 | 0.67 |
| `wildfire_synthesis @ oakland_hills_high` | 3 | 0.64 |

Single-field lookups are perfectly stable. **Multi-field synthesis is not**, which is
exactly what a real agent asks. On one wildfire underwriting query, separate calls
pulled `nearest_fire_station_distance_m`, then `primary_building_footprint_sqm` +
`primary_building_height_m` + `nearest_major_road_distance_m`, then neither.

The product is sold as audit-ready. An audit trail that does not reproduce is not an
audit trail.

**9. Findings 4, 7 and 8 are one chain, not three problems.**
No discovery tool → field-name guessing → forced fallback to `/ask` → error
amplification, where the synthesis layer escalates a medium-confidence
`"Unincorporated"` into the flat assertion *"It does not lie within an incorporated
city"* plus an invented *"near the Presidio."*

---

## What I retracted after checking

Three findings were claimed, then disproved by checking. Two were the benchmark's
fault, not Mireye's. They are listed because a benchmark that cannot survive the
scrutiny it applies is worthless.

**R1. "Systematic planner miss: `fema_base_flood_elevation` missed at 12/12 sites."**
False, and the benchmark's fault. `fields_used` only lists fields that *returned a
value*; a requested field that came back null is reported in `data_gaps` instead. The
planner **did** request the BFE. FEMA simply has no static NAVD88 BFE on that polygon.
Worse for the original claim, Mireye's answer there is the best in the entire run
(question 6 above). `checks/selection.py` was fixed to count fields attempted-but-null.

**R2. "`data_gaps` is never populated."**
False. It populates for null values. The true, narrower finding is finding 4.

**R3. "USGS 3DEP has ~1 m vertical RMSE."**
Imprecise. The figure is 0.82 m (2022). Asserted from memory, then checked and cited.

### Benchmark bugs found by auditing the benchmark

1. Numeric faithfulness counted the echoed input coordinates and the `88` in "NAVD88"
   as unsupported claims, scoring 0.2 on a perfectly faithful answer. Fixed by excluding
   numbers that appear in the question or inside a cited field's own provenance.
2. Selection scored off `fields_used` alone, punishing the planner for missing *data*.
   Fixed. **This bug was slandering the system under test.**
3. Selection penalized correct refusals with `decisive_recall = 0.0`. Fixed.
4. The harness ran one sample per pair, which is invalid given finding 8. Now samples k=3 and
   reports the spread.
5. `DEM_VERTICAL_RMSE_M` was hardcoded from memory. Now cited.

---

## What this does not measure

- The sample is small, 12 coordinates, 9 question types, and weighted toward
  California.
- **The LLM judge did not clear its validation bar in this run.** I hand-labeled a blind
  sample, agreement with my labels came in below 0.8, so every judged number is withheld.
  Everything reported here is deterministic, scored against outside oracles. Validating
  the judge against a larger labeled set is future work.
- The head-to-head uses one baseline model (Opus 4.8) on one day.
- Latency and cost are not measured.
- MCP tool descriptions are from `mireye_earth_mcp` 0.1.0; a newer release may differ.
- `/ask` is non-deterministic and the detailed checks score one sample per pair. The
  stability spread reports how far any single sample can be trusted, but it is still one
  sample.
- This measures reasoning about places against outside oracles where they exist. It is
  not a general audit of whether Mireye's underlying data is correct everywhere.

---

## Reproduce

```bash
pip install -r requirements.txt
cp .env.example .env      # MIREYE_API_KEY; ANTHROPIC_API_KEY for judge + baseline

python3 run.py                 # four-axis run -> results/run.json
python3 tool_choice_run.py     # MCP tool-choice axis -> results/tool_choice.json
python3 report.py              # summary

python3 label.py --n 15        # grade a blind sample by hand
python3 label.py --check       # judge-vs-human agreement, per axis
```

Oracles are queried live and independently. `run.py --no-judge` runs the deterministic
checks with no Anthropic key.
