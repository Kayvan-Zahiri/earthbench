"""Re-run only the head-to-head axis on a saved run. Needs ANTHROPIC_API_KEY.

    python3 rerun_h2h.py --dry-run    # show what would be called
    python3 rerun_h2h.py              # do it

Why this exists. On the 2026-08-05 run the Anthropic key had expired, so all 48
head-to-head records saved `{"error": "401 ..."}` and report.py printed the
section empty. The July figure of 19-3 stood unverified in every document.

Re-running run.py would fix it and also re-measure everything else, which costs
43 minutes, several hundred Mireye calls against a 20 rpm free tier, and makes
the one thing that changed impossible to see. This re-runs the missing half only.

Mireye's own values and the oracle truths are already in the saved records, under
`correctness[].got` and `correctness[].expected`, so neither Mireye nor the
oracles are called again for those. The only new traffic is the model, plus a
live CAL FIRE query for the `fhsz` questions, which have no `correctness` row
because Mireye has no such field. That absence is the finding.

The model is pinned to the same one the July run used, so this is a
re-measurement rather than a different experiment.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from earthbench import baseline                      # noqa: E402
from earthbench.checks import head_to_head           # noqa: E402
from earthbench.fixtures.sites import BY_ID          # noqa: E402
from earthbench.oracles import california            # noqa: E402
from earthbench.judge import MODEL                   # noqa: E402

RUN = pathlib.Path("results/run.json")
# Which Mireye field each comparable question is scored on. `fhsz` has none:
# Mireye does not carry a CAL FIRE hazard class, which is the point of asking.
FIELD = {"elevation": "elevation", "locality": "political_locality",
         "flood_zone": "fema_flood_zone", "fhsz": None}


def saved(rec, field):
    for c in rec.get("correctness") or []:
        if c.get("field") == field:
            return c
    return None


def main() -> int:
    dry = "--dry-run" in sys.argv
    recs = json.loads(RUN.read_text())
    todo = [r for r in recs if "error" in (r.get("head_to_head") or {})]
    print(f"  {len(todo)} head-to-head records to re-run, model {MODEL}\n")
    if dry:
        for r in todo[:6]:
            print(f"    {r['key']}")
        print(f"    ... and {max(0, len(todo)-6)} more")
        return 0

    done = fails = 0
    for i, rec in enumerate(todo, 1):
        qid, sid = rec["question"], rec["site"]
        site = BY_ID[sid]
        field = FIELD.get(qid)
        try:
            if field is None:                       # fhsz: live CAL FIRE, Mireye has nothing
                truth = california.fetch_fhsz(site.lat, site.lng)["calfire_fhsz_class"]["value"]
                m_val = None
            else:
                c = saved(rec, field)
                if c is None or c.get("expected") in (None, ""):
                    raise RuntimeError(f"no saved oracle truth for {field}")
                truth, m_val = c["expected"], c.get("got")

            b = baseline.ask(site.lat, site.lng, rec.get("question_text") or _qtext(qid))
            rec["head_to_head"] = {
                "truth": truth,
                "mireye": m_val,
                "model_refused": b.get("refused"),
                "model_value": b.get("value"),
                "model_confidence": b.get("self_reported_confidence"),
                "outcome": head_to_head.compare(truth, m_val, b.get("refused"), b.get("value")),
                "rerun": "2026-08-08, model only; mireye and oracle values reused from the 2026-08-05 run",
            }
            done += 1
            print(f"  [{i:>2}/{len(todo)}] {rec['key']:<34} {rec['head_to_head']['outcome']}")
        except Exception as exc:
            fails += 1
            rec["head_to_head"] = {"error": str(exc)}
            print(f"  [{i:>2}/{len(todo)}] {rec['key']:<34} FAILED {type(exc).__name__}: {str(exc)[:60]}")
        time.sleep(0.5)

    RUN.write_text(json.dumps(recs, indent=1))
    print(f"\n  {done} scored, {fails} failed. Wrote {RUN}.")
    print("  Now: python3 make_all_answers.py && python3 report.py")
    return 0


def _qtext(qid):
    from earthbench.fixtures.questions import QUESTIONS
    return next(q.text for q in QUESTIONS if q.id == qid)


if __name__ == "__main__":
    sys.exit(main())
