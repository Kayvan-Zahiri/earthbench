# What I built, what I found, and where Mireye is lacking

*The [README](./README.md) covers what it is and
how to run it; this is the thinking behind it and the findings.*

---

## The problem I picked, and why

I didn't pick a use case that consumes Mireye's data. I built the thing that decides
whether anyone should trust it. That feels especially important now, given how much work is being handed to models. It only raises the need to check and verify them.

Mireye's pitch is that agents shouldn't guess about the physical world because you hand
them cited ground truth. That is a claim you can measure, and right now there's not a great way to see whether Mireye holds up. That's why I built this.

So earthbench asks Mireye the questions an agent would ask, then checks the answers
against authorities Mireye doesn't ingest: CAL FIRE, USGS, and FEMA, queried live. This
isn't a use case Google Maps or a GIS analyst could have done instead, because the
subject is Mireye itself. 

## What I asked

Nine questions, the kind an agent actually gets, across 12 real coordinates (75
question-and-place pairs in all). Every answer is scored against an authority Mireye
doesn't ingest.

The questions run from plain lookups ("What city is this?", "Am I in a flood zone?",
"What's the ground elevation?") to underwriting-style synthesis ("I'm underwriting
wildfire risk on a home here, what do I need to know?") to cases where the right answer
is "I can't" ("What's my CAL FIRE Fire Hazard Severity Zone?", which you don't carry,
and "Which of two lots is safer?", which the API can't answer one coordinate at a time).

The coordinates were chosen to stress specific seams: the SF Marina on 1906 fill,
Paradise after the Camp Fire, two points in the same census tract but different fire
zones, Guerneville in a real FEMA flood zone, plus Denver, Manhattan, rural Kansas, and
a point in the open Pacific.

## What I found

**1. The MCP funnels agents into the product's own failure mode.** This is the
one I'd fix first, and it's a chain, not a single bug:

- `mireye_fetch` needs field names from a 255-field catalog, and the MCP exposes no way to discover them (`/v1/meta/fields` exists on the REST API but isn't wired into the MCP). So an agent guesses, and **54% of the field names it asks for aren't real
  fields**: `slope` for `slope_degrees`, `flood_zone` for `fema_flood_zone`.
- Because `fetch` is unusable, the agent falls back on `/ask`: it over-asked on 5 of 8 single-field lookups.
- `/ask` is exactly where a `medium`-confidence `"Unincorporated"` becomes the flat assertion *"It does not lie within an incorporated city,"* plus an invented
  *"near the Presidio."* The synthesis layer amplifies the error instead of damping it.

**The fix:** expose the field catalog as a third MCP tool. 

**2. A raw LLM with no data beats you on some questions, and the citation makes it
worse.** Opus 4.8 with no tools answered "San Francisco" and "Denver" correctly at
high confidence. Mireye returns `"Unincorporated"` for both, *with a federal citation attached*. The citation makes the wrong answer more credible than the right guess. (The field is right for 24 of 28 cities; it fails for county-equivalent ones: SF,
Denver, Baltimore, St. Louis.)

**3. `/ask` is non-deterministic.** Same question, same coordinate, different field
selections across calls. It's stable on simple lookups but not on the multi-field
synthesis a real agent actually asks. For a product you sell as audit-ready, an answer
that doesn't reproduce is the one I'd worry about most.

**4. No state layers, and the gap is structural.** Sources are federal only, so of the
six hazards California legally mandates in a property disclosure, Mireye answers one.
At Paradise (Camp Fire), the wildfire field returns a census-tract average while CAL
FIRE rates the parcel Very High. That gap is *irrecoverable*: one tract holds both High
and NonWildland parcels, so a per-tract number can never separate them.

On the 2026-08-05 re-run, Mireye never gave a false answer in 75 pairs, got the
answer-or-refuse call right 71 of 75 times, and hedged 25 of 25 times it should have.

The head-to-head needed an Anthropic key that had expired, so I re-ran it on
2026-08-08 against the same model. **Mireye wins 23-3.** The moat is real and it is
not close: asked for elevation at the SF Marina the model guessed 90 m against a true
7.52 m, and Mireye returned 7.53 m. Across ten elevation sites the model's median
error was 79 m. It refused every one of the ten flood zone questions.

All three losses are the same field. At SF Marina, SF Mission and Denver, a model with
no data at all names the city correctly at high confidence, while Mireye returns
`"Unincorporated"` with a federal citation attached. That is the sentence I would put
in front of your next design partner: provenance did not prevent the error, it made it
more credible.

The product works. These are the edges.

## What I learned building it

The judge taught me the most. I built an LLM judge to grade the softer calls, the ones
where a regex can't tell whether the wording overreached. However, I didn't trust it just
because it produced numbers. I checked it against my own hand labels first, and it
didn't agree with me well enough to rely on. As a result, I withheld every judged number and kept only the deterministic checks, the ones scored against outside authorities. 

The harness caught four bugs in itself before it caught any in Mireye: a
faithfulness check that counted the echoed input coordinates as claims, a selection
metric that blamed the planner for missing data rather than missing fields, a check
that punished the model for correctly refusing, and a single-run design that was
invalid once I found `/ask` isn't deterministic. All four are written up with the
retractions in AUDIT.md. 

## Where I'd take it next

A few directions, roughly in the order I'd do them:

- **Fix the discovery gap and measure it.** Expose the field catalog as an MCP tool,
  then re-run the tool-choice axis. If the 54% field-name hallucination drops the way I expect, that's a clean before-and-after.
- **Watch it per release.** The head-to-head and the behavior checks are cheap to run.
  Turned into a regression, they'd catch the day a change makes `/ask` start
  hallucinating, or a field quietly breaks.
- **Go past California.** The state-law point isn't really about fire. Anywhere a real
  decision is governed by state or local rules (water rights, zoning, wetlands) the
  federal-only data has the same blind spot, and the same harness would find it.
- **Actually validate the judge.** With a bigger, blind human-labeled set, the
  grounding axis could earn quotable numbers instead of sitting withheld.