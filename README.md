# earthbench

A grounding benchmark for [Mireye](https://www.mireye.com), whose pitch is that AI
agents shouldn't guess about the physical world because Mireye gives them cited,
federal-grade ground truth. 

It measures Mireye's `/ask` and `/fetch` endpoints and its MCP server along four axes
(across nine question types and twelve coordinates), scored against authorities
**outside** Mireye (CAL FIRE, the California Geological Survey, live FEMA NFHL, live
USGS EPQS):

1. **Tool choice**: given the MCP's two tools, does an agent pick the right one, and
   can it name the fields it needs?
2. **Field selection**: does Mireye's own `/ask` planner pull the decisive field?
3. **Grounding**: split in two:
   - **faithfulness**: does the prose follow from the fields it cited?
   - **correctness**: do the fields follow from the world?
4. **Uncertainty**: does it refuse when it should, hedge when it should, and report
   what it's missing?

Plus a head-to-head: Mireye vs a raw LLM with no data, scored on the same oracles.

Every headline number is deterministic. An LLM judge grades the semantic questions a
regex can't, and it is **only quoted after being validated against hand labels** (see
[Judge](#the-judge)).

The reasoning behind it, and what it means, is in [WRITEUP.md](./WRITEUP.md).

## Headlines

The full findings, and what they mean, are in [WRITEUP.md](./WRITEUP.md). In brief:

- **Where Mireye is strong.** It wins the head-to-head against a
  no-data LLM **19-3**, never gave a false answer across 75 pairs, and hedges when it
  should. The findings below are about the edges, not the core.
- **The MCP has no field-discovery tool, and the agent pays for it.** With no way to
  list the 255 fields, an agent guessing field names gets **54% of them wrong** (21 of
  39), then falls back to `/ask`, where a shaky value can get restated with more
  confidence. Exposing `/v1/meta/fields` as one more MCP tool would close most of this.
- **On a couple of questions a no-data LLM does better, which points to a narrow bug.**
  Asked "what city is this?", a raw model answers "San Francisco" and "Denver"
  correctly, while Mireye returns `"Unincorporated"` for county-equivalent cities (SF,
  Denver, Baltimore, St. Louis). The field is right for 24 of 28 cities, so the fix is
  small.
- **Federal-only sourcing leaves a structural gap in state-governed decisions.** In
  California, the hazard maps that carry legal weight (CAL FIRE, CGS) are state-owned,
  so an agent underwriting wildfire at Paradise gets a census-tract average where the
  parcel-level answer is what matters.

## Results

75 (question, site) pairs, `/ask` sampled k=3 (it is non-deterministic, see below).

| axis | result |
|---|---|
| Head-to-head vs no-data LLM | Mireye **19-3** |
| Correct answer/refuse behavior | 71/75 (**95%**) · **0 false answers** |
| Hedged when it should | 24/25 (96%) |
| `/ask` decisive-field recall | **1.000** |
| `fema_flood_zone` correctness | 68/68 (100%) |
| `political_locality` correctness | 32/50 (64%) |
| MCP field-name hallucination | **21/39 (54%)** |
| MCP over-ask on lookups | 5/8 |

**`/ask` is non-deterministic.** Identical question, identical coordinate, different
field selections across calls. Stable on single-field lookups, unstable on the
multi-field synthesis a real agent actually asks. For a product sold as *audit-ready*,
a decision that doesn't reproduce is the finding that matters most.

Elevation correctness is left out of the table on purpose. Mireye's elevation is
accurate: 9 of the 11 land sites agree with a live USGS query within 0.6 m, and the two
that don't are steep hillsides where the DEM itself is least accurate (3DEP RMSE 0.82 m).
The real elevation issue is *precision*, not accuracy: it's reported to the centimetre
with no error bar, which reads as exact when it isn't.

## Reproduce

```bash
pip install -r requirements.txt
cp .env.example .env      # add MIREYE_API_KEY; ANTHROPIC_API_KEY for judge + baseline

python3 run.py                 # the four-axis run -> results/run.json
python3 tool_choice_run.py     # the MCP tool-choice axis -> results/tool_choice.json
python3 report.py              # summary
```

Oracles are queried live and independently, so the harness scores Mireye against
something outside it, never against its own cache. `run.py --no-judge` runs the
deterministic checks with no Anthropic key.

## The judge

The deterministic checks catch blatant failures; semantic ones ("is this an invented
claim or a restated definition?") need judgment. So there's an LLM judge, and it is
**never trusted on its own.** `label.py` collects human labels on a blind sample, and
`report.py` withholds every judged number until `label.py --check` shows the judge
agrees with the human at ≥0.8 per axis.

```bash
python3 label.py --n 15     # grade a sample yourself, blind to the judge
python3 label.py --check    # judge-vs-human agreement, per axis
```

In this run, the judge did not clear that bar. I hand-labeled a sample, its agreement
with my labels came in below 0.8, so every judged number is withheld and everything
reported here comes from the deterministic checks against outside oracles. Validating
the judge properly, with a larger blind labeled set, is future work.

## What this does not measure

- The sample is small (12 coordinates, 9 question types) and weighted toward California.
- The LLM judge isn't validated, so its grounding numbers are withheld; everything
  reported is deterministic.
- The head-to-head uses one baseline model (Opus 4.8) on one day.
- Latency and cost aren't measured.
- The MCP tool descriptions are from `mireye_earth_mcp` 0.1.0; a newer release may read
  differently.
- `/ask` is non-deterministic, and the detailed checks score one sample per pair. The
  stability spread reports how much any single sample can be trusted, but it's still one
  sample.
- This measures reasoning about places against outside oracles where they exist. It is
  not a general audit of whether Mireye's underlying data is correct everywhere.
