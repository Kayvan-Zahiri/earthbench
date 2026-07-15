"""Summarize a run into the numbers you would actually say out loud.

    python3 report.py
"""

import collections
import json
import pathlib

RUN = pathlib.Path("results/run.json")


def pct(n, d):
    return f"{100*n/d:.0f}%" if d else "n/a"


def main():
    recs = [r for r in json.loads(RUN.read_text()) if not r.get("error")]
    print(f"EARTHBENCH  |  {len(recs)} (question, site) pairs\n")

    # ---- Head to head: Mireye vs a model with no data, same oracle -------------
    h2h = [r["head_to_head"] for r in recs
           if isinstance(r.get("head_to_head"), dict) and "outcome" in r["head_to_head"]]
    tally = collections.Counter(x["outcome"] for x in h2h)
    print("HEAD TO HEAD  (Mireye vs raw Opus 4.8 with no data, scored on the same oracle)")
    for k in ("mireye_wins", "model_wins", "both_right", "both_refuse", "both_wrong", "no_oracle"):
        if tally[k]:
            print(f"  {k:<14} {tally[k]:>3}   {pct(tally[k], len(h2h))}")
    losses = [r for r in recs
              if (r.get("head_to_head") or {}).get("outcome") == "model_wins"]
    if losses:
        print("\n  MIREYE LOST TO A MODEL WITH NO DATA ON:")
        for r in losses:
            hh = r["head_to_head"]
            print(f"    {r['key']:<26} truth={hh['truth']!r}  mireye={hh['mireye']!r}  "
                  f"model={hh['model_value']!r} ({hh['model_confidence']})")
        print("\n  Mireye's wrong answer ships with a federal citation attached.")
        print("  The model's right answer does not. Provenance made the error MORE credible.")

    # ---- Axis 3: did it know what it didn't know? ------------------------------
    print("\nUNCERTAINTY")
    ok = sum(1 for r in recs if r["uncertainty"]["correct_behavior"])
    fr = sum(1 for r in recs if r["uncertainty"]["false_refusal"])
    fa = sum(1 for r in recs if r["uncertainty"]["false_answer"])
    print(f"  correct answer/refuse behavior   {ok}/{len(recs)}  {pct(ok, len(recs))}")
    print(f"  false refusals                   {fr}")
    print(f"  false answers                    {fa}")

    need_hedge = [r for r in recs if r["uncertainty"]["hedge_required"]]
    hedged = sum(1 for r in need_hedge if r["uncertainty"]["hedged_lexical"])
    print(f"  hedged when it should            {hedged}/{len(need_hedge)}  {pct(hedged, len(need_hedge))}")

    gaps = [r for r in recs if r["question"] == "fhsz"]
    gp = sum(1 for r in gaps if r["uncertainty"]["data_gaps_populated"])
    print(f"  data_gaps populated on a real")
    print(f"    COVERAGE gap (CAL FIRE)        {gp}/{len(gaps)}   <- reports null values, not missing datasets")

    # ---- Axis 1: field selection ----------------------------------------------
    sel = [r["selection"] for r in recs if r["selection"].get("decisive_recall") is not None]
    if sel:
        dr = sum(s["decisive_recall"] for s in sel) / len(sel)
        misses = [r for r in recs
                  if r["selection"].get("decisive_recall") not in (None, 1.0)]
        print("\nFIELD SELECTION  (Mireye's own planner)")
        print(f"  mean decisive-field recall       {dr:.3f}")
        for r in misses:
            print(f"    MISSED  {r['key']:<26} {r['selection']['missed_decisive']}")

    # ---- Axis 2b: are the fields true? ----------------------------------------
    print("\nCORRECTNESS  (fields vs outside authorities)")
    by_field = collections.defaultdict(lambda: [0, 0])
    for r in recs:
        for c in r.get("correctness") or []:
            if c.get("correct") is None or "error" in c:
                continue
            by_field[c["field"]][1] += 1
            by_field[c["field"]][0] += bool(c["correct"])
    for f, (ok_, n) in sorted(by_field.items()):
        print(f"  {f:<24} {ok_}/{n}  {pct(ok_, n)}")

    # ---- Judge, only if it earned the right to be quoted ------------------------
    val = pathlib.Path("results/judge_validation.json")
    print("\nJUDGE")
    if not val.exists():
        print("  NOT VALIDATED. Run label.py, then label.py --check.")
        print("  Judged numbers are withheld until the judge is checked against human labels.")
    else:
        v = json.loads(val.read_text())
        for f, r in v.items():
            mark = "quotable" if r["agreement"] >= 0.8 else "WITHHELD (below 0.8)"
            print(f"  {f:<22} agreement={r['agreement']}  n={r['n']}  {mark}")


if __name__ == "__main__":
    main()
