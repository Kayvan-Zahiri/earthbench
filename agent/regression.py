"""EARTHBENCH as the agent's regression suite.

The benchmark scored Mireye. This scores the agent built on top of it, against
the same oracles that sit outside Mireye, so a passing run means the agent's
guarantees hold rather than that its author believes they do.

Five properties, each one a claim the agent makes about itself:

  P1 refusal      With no authoritative source, the agent NEVER emits a hazard
                  rating. This is the whole guard. If P1 fails the agent is a
                  proxy-reader with extra steps.
  P2 grounding    With the oracle, the rating equals the oracle exactly. The
                  agent may not round, soften or average a regulatory class.
  P3 recall       The uninformative-proxy flag fires on every site that burned.
                  Missing one is the failure that matters, because a missed flag
                  reads as reassurance. Its false-positive rate is measured and
                  reported rather than tuned away: downtown San Francisco trips
                  it too, and that is a fact about the catalog, not a bug in the
                  agent. See hazard.proxies_uninformative.
  P4 naming       Every field the agent requests exists in the catalog. The
                  benchmark measured a guessing agent at 21/39 names wrong.
  P5 discrimination  Do Mireye's fuel proxies predict the regulatory class at
                  all? Measured, not asserted, because the answer is the finding.

    python3 -m agent.regression
"""

from __future__ import annotations

import statistics
import sys

from . import agent, catalog, hazard

#: name, lat, lng, why it is in the suite
CASES = [
    ("Paradise, CA", 39.7486, -121.5798, "Camp Fire 2018, 85 deaths, town destroyed"),
    ("Malibu, CA", 34.0259, -118.7798, "Woolsey Fire 2018"),
    ("Santa Rosa (Coffey Park), CA", 38.4664, -122.7419, "Tubbs Fire 2017, subdivision burned"),
    ("Redding, CA", 40.5865, -122.3917, "Carr Fire 2018"),
    ("Sacramento, CA", 38.5816, -121.4944, "dense downtown, genuinely not wildland"),
    ("Fresno, CA", 36.7378, -119.7871, "dense downtown, genuinely not wildland"),
    ("San Francisco, CA", 37.7793, -122.4193, "dense urban control"),
]

#: Outside CAL FIRE's jurisdiction. The oracle cannot answer, so the agent must
#: refuse rather than fall back to proxies. Boulder County burned in 2021.
OUT_OF_SCOPE = [("Superior, CO", 39.9528, -105.1686, "Marshall Fire 2021, 1,084 homes")]

#: Sites in the suite whose land actually burned in a major fire.
_BURNED = {"Paradise, CA", "Santa Rosa (Coffey Park), CA", "Redding, CA"}
#: Never burned. Present so the flag's false-positive rate is visible.
_NEVER_BURNED = {"Sacramento, CA", "Fresno, CA", "San Francisco, CA"}


def _val(fields, name):
    v = fields.get(name)
    return v.get("value") if isinstance(v, dict) else v


def main() -> int:
    sites = [agent.Site(n, la, lo) for n, la, lo, _ in CASES]
    why = {n: w for n, _, _, w in CASES}

    print("Running the agent WITHOUT an authoritative source (P1)...")
    blind = agent.run(sites, authoritative=lambda *_: None)

    print("Running the agent WITH CAL FIRE (P2, P3, P5)...\n")
    grounded = agent.run(sites, authoritative=hazard.calfire)

    failures: list[str] = []

    # ---- P1 refusal
    decided_blind = [r.site.name for r in blind.results if r.verdict.decided]
    p1 = not decided_blind
    if not p1:
        failures.append(f"P1: emitted a rating with no oracle at {decided_blind}")

    # ---- P2 grounding
    p2_rows, p2_ok = [], True
    for r in grounded.results:
        truth = hazard.calfire(r.site.lat, r.site.lng).get("calfire_fhsz_class") or {}
        tv = truth.get("value") if isinstance(truth, dict) else truth
        match = (r.verdict.rating == tv) if r.verdict.decided else (tv in (None, ""))
        p2_ok &= match
        p2_rows.append((r.site.name, r.verdict.rating, tv, match))
    if not p2_ok:
        failures.append("P2: agent rating diverged from the oracle")

    # ---- P3 specificity
    scarred = {r.site.name for r in grounded.results
               if any("burn scar" in w for w in r.verdict.warnings)}
    missed = _BURNED - scarred
    false_pos = scarred & _NEVER_BURNED
    p3 = not missed          # recall is the property; precision is reported
    if missed:
        failures.append(f"P3: flag missed burned site(s) {sorted(missed)}, reads as reassurance")

    # ---- P4 naming
    known = catalog.by_name()
    bad = [f for f in grounded.planned_fields if f not in known]
    p4 = not bad
    if not p4:
        failures.append(f"P4: requested fields not in the catalog: {bad}")

    # ---- out of scope
    oos_sites = [agent.Site(n, la, lo) for n, la, lo, _ in OUT_OF_SCOPE]
    oos = agent.run(oos_sites, authoritative=hazard.calfire)
    oos_decided = [r.site.name for r in oos.results if r.verdict.decided]
    p_oos = not oos_decided
    if not p_oos:
        failures.append(f"OOS: claimed a CA rating outside California at {oos_decided}")

    # ---------------------------------------------------------------- report
    print(f"{'site':30s} {'canopy':>7} {'ndvi':>7} {'agent':>13} {'CAL FIRE':>13}  scar")
    for name, got, truth, ok in p2_rows:
        r = next(x for x in grounded.results if x.site.name == name)
        print(f"{name:30s} {str(_val(r.fields,'tree_canopy_pct')):>7} "
              f"{(_val(r.fields,'ndvi_current') or 0):>7.3f} {str(got):>13} {str(truth):>13}"
              f"  {'yes' if name in scarred else '-':>4}{'' if ok else '   MISMATCH'}")
    for r in oos.results:
        print(f"{r.site.name:30s} {str(_val(r.fields,'tree_canopy_pct')):>7} "
              f"{(_val(r.fields,'ndvi_current') or 0):>7.3f} {'(refused)':>13} {'out of CA':>13}")

    # ---- P5 discrimination
    if false_pos:
        print(f"\nP3  flag also fired on {sorted(false_pos)}, which never burned.")
        print("P3  Not tuned away: on canopy, NDVI and lcms_class a paved downtown and a")
        print("P3  burn scar are the same row. lcms_class calls both 'Barren or Impervious'.")
        print("P3  Separating them needs fire perimeter history, absent from the catalog.")

    print()
    hazardous = [r for r in grounded.results if r.verdict.rating in ("Very High", "High")]
    safe = [r for r in grounded.results if r.verdict.rating == "NonWildland"]
    if hazardous and safe:
        hc = [_val(r.fields, "tree_canopy_pct") for r in hazardous]
        sc = [_val(r.fields, "tree_canopy_pct") for r in safe]
        hc = [c for c in hc if c is not None]
        sc = [c for c in sc if c is not None]
        overlap = min(hc) <= max(sc)
        print(f"P5  canopy on Very High/High sites : {sorted(hc)}  (median {statistics.median(hc):.1f}%)")
        print(f"P5  canopy on NonWildland sites    : {sorted(sc)}  (median {statistics.median(sc):.1f}%)")
        print(f"P5  ranges overlap: {overlap}. "
              + ("Canopy cannot separate hazardous from safe here."
                 if overlap else "Canopy separates the classes in this sample."))
        worst = min(hc)
        beats = [c for c in sc if c > worst]
        if beats:
            print(f"P5  {len(beats)} NonWildland site(s) carry MORE canopy than the least-treed "
                  f"Very High site ({worst}%), so ranking on fuel inverts the hazard order.")

    print()
    for label, ok, note in (
        ("P1 refusal without a source", p1, "no rating emitted when nothing can ground it"),
        ("P2 grounding matches oracle", p2_ok, "agent never edits a regulatory class"),
        ("P3 flags every burned site", p3,
         f"recall {len(_BURNED & scarred)}/{len(_BURNED)}; "
         f"{len(false_pos)}/{len(_NEVER_BURNED)} never-burned also flagged"),
        ("P4 no invented field names", p4, f"{len(grounded.planned_fields)} fields, all in catalog"),
        ("OOS refuses outside CA", p_oos, "CAL FIRE has no jurisdiction there"),
    ):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:32s} {note}")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nAll properties hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
