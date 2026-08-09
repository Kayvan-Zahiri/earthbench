# earthbench: an agent that refuses to price what it cannot see

**Repo:** https://github.com/Kayvan-Zahiri/earthbench · **Kayvan Zahiri**, San Francisco

---

## The problem

Mireye's `wildfire_underwrite` preset rates **Paradise, California as low fuel.**

Paradise burned in the 2018 Camp Fire. Eighty-five people died. CAL FIRE still
rates it **Very High**.

The preset is not wrong about the numbers. Canopy really is 1%, NDVI really is
0.11. It is wrong about what they mean: the town is bare *because* it burned. Any
agent that ranks parcels on those six proxies will hand an underwriter Paradise
as a safe bet.

This is not a corner case. Measured live across eight California sites:

```
canopy on Very High / High sites : [1.0, 15.0]                median 8.0%
canopy on NonWildland sites      : [0.0, 1.0, 1.0, 2.0, 8.0]  median 1.0%
```

The ranges **overlap**, and two NonWildland sites carry more canopy than the
least-treed Very High site. Ranking on fuel does not lose signal, it inverts the
order.

## What I built

An agent that plans, fetches, decides, and refuses.

1. **Plans fields from your catalog, not from guesses.** It reads `presets` and
   `interpretation_hints` off `/v1/meta/fields`. My benchmark measured an agent
   guessing field names wrong **21 times out of 39** when it had no way to list
   them; planning from the catalog is why this agent invents none.
2. **Batches candidates** through `POST /v1/fetch/batch`.
3. **Applies the thresholds your hints state**, not thresholds it invented.
4. **Will not call hazard from fuel proxies.** It requires an authoritative
   rating, finds the catalog has none, files a `POST /v1/field-requests` for the
   missing fields, and falls back to CAL FIRE.
5. **Reports what would change its answer.**

On Paradise it returns Very High, states that Mireye's proxies disagree, and
explains that canopy 1% / NDVI 0.11 / "Grass/Forb/Herb" is equally consistent
with a burn scar, bare ground and pavement, so it is not evidence of low hazard
in either direction.

## Why you can believe it

`agent/regression.py` asserts five properties against oracles **outside** Mireye
(CAL FIRE, CGS, live FEMA NFHL, live USGS EPQS) and passes all five live:
refusal without a source, grounding matches the oracle, 3/3 recall on sites that
actually burned, zero invented field names, and refusal outside California where
CAL FIRE has no jurisdiction.

One property is deliberately **not** tuned. The burn-scar flag also fires on San
Francisco, which never burned, because on canopy, NDVI and `lcms_class` a paved
downtown and a burn scar are the same row: `lcms_class` calls both "Barren or
Impervious." Tuning that away would hide the finding rather than fix it.

Underneath sits the benchmark this grew out of: 75 (question, site) pairs scoring
`/ask`, `/fetch` and the MCP server against outside authorities. It found Mireye
**beats a no-data LLM 23-3 with zero false answers**. The core is strong; the
findings are about the edges. The head-to-head was re-run 2026-08-08 and the
rest measured 2026-08-05; the agent results above are live as of 2026-08-05.

## Who writes the cheque

**California wildfire underwriters and the carriers behind them.** FAIR Plan
exposure has grown every year since 2018 and admitted carriers have withdrawn
from whole counties. A parcel-level hazard call that is *defensible* is worth
real money, because the alternative is pricing blind or not writing at all.

Adjacent, same shape: **utility siting and vegetation management** (PG&E-scale
liability), **CRE lenders** requiring hazard diligence, and **solar/data-centre
siting** teams already using your `site_selection` and `data_center_siting`
presets.

What they buy is not the data. It is a decision they can put in a file and
defend. That needs three things Mireye has two of: the ground truth, the
comparison, and the refusal.

## What I would want from Mireye

`fire_hazard_severity_zone`, `burn_probability`, `wildfire_risk_to_homes`, and
`dist_to_wui_m`, the last of which your own `slope_degrees` hint already tells
agents to combine with, though it does not exist. Fire perimeter history would
let the agent separate a burn scar from a parking lot, which is the one thing
standing between this and a clean answer.
