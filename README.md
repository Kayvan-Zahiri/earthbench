# earthbench

**An agent that prices wildfire risk on [Mireye](https://www.mireye.com) data, and
refuses to answer when Mireye's data cannot support an answer.**

Mireye's own `wildfire_underwrite` preset rates **Paradise, California as low
fuel**. Paradise burned in the 2018 Camp Fire and 85 people died. CAL FIRE still
rates it **Very High**. The preset is not wrong about the numbers, canopy really
is 1%, NDVI really is 0.11. It is wrong about what they mean. The town is bare
*because* it burned.

That is the failure this agent exists to not repeat.

```
--- Paradise, CA (Camp Fire 2018)
    canopy 1.0%   ndvi 0.109   cover Grass/Forb/Herb   slope 4.14
    Very High: CAL FIRE Fire Hazard Severity Zone, the map California insurers
    price against. Mireye's fuel proxies read low at this site and disagree
    flag: canopy 1.0%, NDVI 0.109, cover 'Grass/Forb/Herb'. These values are
    equally consistent with a burn scar, with bare ground that never carried
    fuel, and with pavement. The catalog cannot separate them, so this is not
    evidence of low hazard in either direction.
    would change the answer: fire perimeter history, to tell a burn scar from
    pavement
```

Every number above is fetched live.

## What it does

1. **Plans fields from the catalog, not from guesses.** It reads `presets` and
   `interpretation_hints` off `/v1/meta/fields`. The benchmark below measured an
   agent guessing field names wrong **21 times out of 39** when it had no way to
   list them, which is why this step exists. The agent plans 6 fields and all 6
   exist (P4), a smaller and easier test than the benchmark's, not the same one
   scored again.
2. **Fetches all candidates in one call** via `POST /v1/fetch/batch`.
3. **Applies the thresholds the hints state** instead of inventing its own
   (`slope_degrees`: *"Slope >15° materially raises wildfire spread risk"*).
4. **Refuses to conclude hazard from fuel proxies.** It requires an authoritative
   rating, finds Mireye has none, files a `POST /v1/field-requests` for the
   missing fields, and falls back to CAL FIRE.
5. **Says what would change its mind.**

## The finding that justifies step 4

`wildfire_underwrite` is six fuel and terrain proxies with no hazard rating:
`elevation`, `slope_degrees`, `lcms_class`, `tree_canopy_pct`, `ndvi_current`,
`ndvi_change_5y`. There is no `fire_hazard_severity_zone`, no `burn_probability`
and no `wildfire_risk_to_homes` among the 283 published fields.

Ranking on those proxies does not merely lose signal, **it inverts the order**.
Measured live across eight sites:

```
canopy on Very High / High sites : [1.0, 15.0]                median 8.0%
canopy on NonWildland sites      : [0.0, 1.0, 1.0, 2.0, 8.0]  median 1.0%
ranges overlap: True
```

Two NonWildland sites carry **more** canopy than the least-treed Very High site.
An underwriter ranking parcels on tree cover would rate Paradise safer than
downtown Sacramento.

A related gap: the hint on `slope_degrees` tells you to *"combine with
`lcms_class` and `dist_to_wui_m`"*. There is no `dist_to_wui_m`, or anything
matching WUI, in the catalog. Distance to the wildland-urban interface is the
central variable in wildfire underwriting and the documentation assumes it ships.

## The regression suite

`agent/regression.py` runs the agent against oracles outside Mireye and asserts
five properties. It runs live and currently passes all five.

| property | what it pins |
| --- | --- |
| P1 refusal without a source | emits no rating at all when nothing can ground it |
| P2 grounding matches oracle | never edits a regulatory class it was handed |
| P3 flags every burned site | recall 3/3 on sites that actually burned |
| P4 no invented field names | all 6 planned fields exist in the catalog |
| OOS refuses outside CA | declines Superior, CO, where CAL FIRE has no jurisdiction |

**P3 is deliberately not tuned.** The flag also fires on San Francisco, which has
never burned. That is honest rather than fixable: on canopy, NDVI and
`lcms_class`, a paved downtown and a burn scar are the same row: `lcms_class`
calls both *"Barren or Impervious"*. Separating them needs fire perimeter
history, which the catalog does not carry. Tuning the flag to hide that would be
tuning away the finding.


## Four agent patterns, in one system that had to work

These get built as separate demo repos. Here they are load-bearing in something
with a real failure mode, which is where the interesting parts show up.

| pattern | where it lives | the part that is not decorative |
| --- | --- | --- |
| **Citation grounding** | `agent/hazard.py:53`; every `Verdict` carries a `basis` | the basis names the *source*, not the field. A rating sourced from Mireye's own proxies is not grounding, it is restating the input |
| **Plan → act → decide, with refusal** | `agent/agent.py:60` `plan` → `:68` `gather` → `hazard.assess` → `:148` `run` | the loop can terminate in "no verdict". `Verdict.line()` prints `NO VERDICT: <why>` rather than a hedged number |
| **Uncertainty → escalation** | `agent/agent.py:49` `missing_decisive`, `:93` `file_field_request` | it does not just flag low confidence. It identifies which field would settle the question, files a request for it, and records the ask when the plan cannot file one |
| **LLM judge with validation** | `earthbench/judge.py:117` `validate`, gated in `report.py:90` | judged numbers are **withheld** below 0.8 agreement with hand labels. On the 2026-08-05 run every judge metric fell below that and was withheld, which is the point: an unvalidated judge is a number you cannot use |

The last one is the one usually skipped. Running an LLM-as-judge is easy;
knowing whether to believe it is the work, and the honest outcome is sometimes
that you cannot.

## Running it

```bash
pip install -r requirements.txt
export MIREYE_API_KEY=...
python3 -m agent.demo        # four California parcels, live
python3 -m agent.regression  # the five properties, live
```

## The benchmark underneath

Before the agent there was a benchmark: does Mireye's output survive contact with
authorities outside it? It scores `/ask`, `/fetch` and the MCP server on tool
choice, field selection, grounding and uncertainty, against CAL FIRE, the
California Geological Survey, live FEMA NFHL and live USGS EPQS. 75 (question,
site) pairs.

**Re-run live on 2026-08-05** against the current 283-field catalog, 43 minutes,
0 failed pairs:

| axis | 2026-07-13 | 2026-08-05 |
|---|---|---|
| Correct answer/refuse behaviour | 71/75 (95%) | **71/75 (95%)** |
| False answers | 0 | **0** |
| Hedged when it should | 24/25 (96%) | **25/25 (100%)** |
| `/ask` decisive-field recall | 1.000 | **1.000** |
| `fema_flood_zone` correctness | 68/68 (100%) | **58/58 (100%)** |
| `political_locality` correctness | 32/50 (64%) | **26/50 (52%)** |
| Head-to-head vs a no-data LLM | 19-3 | **23-3** (re-run 2026-08-08) |

**`/ask` is still non-deterministic.** Identical question, identical coordinate,
different field selections across calls. For a product sold as *audit-ready*, a
decision that does not reproduce is the finding that matters most.

**`political_locality` got worse, not better.** San Francisco, Denver,
Baltimore and St. Louis still return `"Unincorporated"`, and Manhattan has
changed from `"New York"` to `"Manhattan"`, which is new since July.

Two caveats stated rather than buried. The head-to-head needed an Anthropic key
that had expired on 2026-08-05, so it was re-run on 2026-08-08 with the same
model: **Mireye wins 23-3**, and all three losses are `political_locality` at
SF Marina, SF Mission and Denver, where a model with no data at all gets the
city right at high confidence and Mireye returns `"Unincorporated"` with a
federal citation. Seven of the 48 pairs could not be scored because the saved
oracle value was empty, and they are reported as `no_oracle` rather than as
wins. The **LLM judge remains withheld**, not for want of a key but because it
agreed with hand labels below 0.8. And the 10 `fema_flood_zone` records excluded above are ones
where the live FEMA oracle returned nothing; scoring them as Mireye errors is a
bug this run exposed and [`correctness.py`](./earthbench/checks/correctness.py)
now marks them skipped instead. Before that fix the same data read as an 85%
regression that had not happened.

The benchmark is why the agent is shaped this way. Its finding #7 was that Mireye
has no decision primitive: nothing that ranks, compares or refuses. The agent is
the layer the benchmark showed was missing.

## Reproducing the benchmark

```bash
cp .env.example .env      # MIREYE_API_KEY; ANTHROPIC_API_KEY for judge + baseline
python3 run.py                 # four-axis run -> results/run.json
python3 tool_choice_run.py     # MCP tool-choice axis -> results/tool_choice.json
python3 report.py              # summary
python3 rescore.py             # re-apply current check rules to a saved run
```

## The rest of the writing

| doc | what it is |
| --- | --- |
| [ONEPAGER.md](./ONEPAGER.md) | the one-pager: the problem, the agent, the finding |
| [FEEDBACK.md](./FEEDBACK.md) | eight things Mireye could fix, ranked, verified live |
| [WRITEUP.md](./WRITEUP.md) | what I built, what broke, what I got wrong |
| [AUDIT.md](./AUDIT.md) | every claim, and the four I retracted after checking |
| [FULL_REPORT.md](./FULL_REPORT.md) | the long version, with verbatim answers |
| [ALL_ANSWERS.md](./ALL_ANSWERS.md) | all 75 pairs, every answer Mireye gave, unedited |
