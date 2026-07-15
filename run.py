"""Run the benchmark.

    python3 run.py            # full run -> results/run.json
    python3 run.py --quick    # one site per question, smoke test
    python3 run.py --no-judge # skip the LLM judge (deterministic checks only)

Every headline number here is deterministic. The API's own response envelope says
whether it refused. Outside oracles (CAL FIRE, CGS, live FEMA, live USGS) say
whether the fields are true. The LLM judge is a second opinion on the semantic
questions a regex cannot settle, and it is never the only opinion: label.py
collects human labels and judge.validate() reports how far the judge can be
trusted. If that agreement is weak, the judged numbers do not get quoted.
"""

import argparse
import json
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor

from earthbench import baseline, judge, mireye
from earthbench.checks import correctness, grounding, head_to_head, selection, uncertainty
from earthbench.fixtures.questions import QUESTIONS
from earthbench.fixtures.sites import BY_ID, SITES
from earthbench.oracles import california, federal

RESULTS = pathlib.Path("results")
WORKERS = 4   # their API is free and in early access; be a good guest

# Head-to-head only runs where a question has ONE extractable value and an oracle.
# The synthesis questions (wildfire, fuel) have no single right answer, so they are
# scored on the other axes and left out of this table rather than fudged into it.
COMPARABLE = {
    "elevation":  ("elevation", lambda s: federal.usgs_elevation_m(s.lat, s.lng)),
    "locality":   ("political_locality", lambda s: s.truth.get("locality")),
    "flood_zone": ("fema_flood_zone", lambda s: federal.fema_flood_zone(s.lat, s.lng)),
    "fhsz":       (None, lambda s: california.fetch_fhsz(s.lat, s.lng)["calfire_fhsz_class"]["value"]),
}


def pairs(quick):
    for q in QUESTIONS:
        sites = [BY_ID[s] for s in q.sites] if q.sites else SITES
        yield from ((q, s) for s in (sites[:1] if quick else sites))


def run_one(args):
    q, s, use_judge, k = args
    rec = {"key": f"{q.id}@{s.id}", "question": q.id, "site": s.id,
           "axis": q.axis, "expect": q.expect}

    # /ask is NOT deterministic: identical inputs produce different prose and, more
    # seriously, DIFFERENT FIELD SELECTIONS. So a single call is a sample, not a
    # measurement. We take k samples and report the spread alongside the result.
    samples = []
    for _ in range(k):
        t0 = time.perf_counter()
        try:
            r = mireye.ask(s.lat, s.lng, q.text)
        except Exception as exc:
            rec.setdefault("sample_errors", []).append(str(exc))
            continue
        samples.append({
            "answer": r.get("answer"),
            "confidence": r.get("confidence"),
            "fields_used": r.get("fields_used") or [],
            "data_gaps": r.get("data_gaps") or [],
            "citations": r.get("citations") or [],
            "latency_s": round(time.perf_counter() - t0, 2),
            "behavior": uncertainty.behavior(r),
        })

    if not samples:
        rec["error"] = "all samples failed"
        return rec

    field_sets = [frozenset(x["fields_used"]) for x in samples]
    union = set().union(*field_sets)
    inter = set.intersection(*[set(f) for f in field_sets])
    rec["stability"] = {
        "k": len(samples),
        "distinct_field_sets": len({fs for fs in field_sets}),
        "field_jaccard": round(len(inter) / len(union), 3) if union else 1.0,
        "distinct_answers": len({(x["answer"] or "")[:400] for x in samples}),
        "distinct_behaviors": sorted({x["behavior"] for x in samples}),
        "deterministic": len({fs for fs in field_sets}) == 1,
    }

    # Detailed checks run against sample 0; the spread above says how much to
    # trust any single-sample number.
    s0 = samples[0]
    resp = {"answer": s0["answer"], "confidence": s0["confidence"],
            "fields_used": s0["fields_used"], "citations": s0["citations"],
            "data_gaps": s0["data_gaps"]}

    rec["latency_s"] = s0["latency_s"]
    rec["answer"] = s0["answer"]
    rec["confidence"] = s0["confidence"]
    rec["fields_used"] = s0["fields_used"]
    rec["data_gaps"] = s0["data_gaps"]
    rec["n_citations"] = len(s0["citations"])

    rec["uncertainty"] = uncertainty.score(resp, q.expect)
    rec["selection"] = selection.score(
        rec["fields_used"], q.gold_fields, q.decisive,
        data_gaps=rec["data_gaps"],
        refused=(rec["uncertainty"]["behavior"] == "refuse"),
    )

    used = {}
    if rec["fields_used"]:
        try:
            used = mireye.fetch(s.lat, s.lng, rec["fields_used"])
            rec["grounding"] = grounding.score(rec["answer"], used, q.text, s.lat, s.lng)
        except Exception as exc:
            rec["grounding"] = {"error": str(exc)}

    try:
        gold = sorted(q.gold_fields | {"political_locality", "elevation",
                                       "fema_flood_zone", "wildfire_annual_frequency"})
        fetched = mireye.fetch(s.lat, s.lng, gold)
        rec["correctness"] = correctness.score(s, fetched)
    except Exception as exc:
        fetched = {}
        rec["correctness"] = [{"error": str(exc)}]

    # Head to head against a model with no data, scored on the same oracle.
    if q.id in COMPARABLE:
        field, oracle = COMPARABLE[q.id]
        try:
            truth = oracle(s)
            b = baseline.ask(s.lat, s.lng, q.text)
            m_val = (fetched.get(field) or {}).get("value") if field else None
            rec["head_to_head"] = {
                "truth": truth,
                "mireye": m_val,
                "model_refused": b.get("refused"),
                "model_value": b.get("value"),
                "model_confidence": b.get("self_reported_confidence"),
                "outcome": head_to_head.compare(truth, m_val, b.get("refused"), b.get("value")),
            }
        except Exception as exc:
            rec["head_to_head"] = {"error": str(exc)}

    if use_judge and rec.get("answer") and used:
        try:
            rec["judge"] = judge.grade(q.text, rec["answer"], used)
        except Exception as exc:
            rec["judge"] = {"error": str(exc)}

    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--samples", type=int, default=3,
                    help="/ask is nondeterministic; k samples per pair")
    args = ap.parse_args()

    todo = [(q, s, not args.no_judge, args.samples) for q, s in pairs(args.quick)]
    print(f"{len(todo)} pairs x {args.samples} samples, {WORKERS} workers, "
          f"judge={'off' if args.no_judge else 'on'}\n")

    out = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for i, rec in enumerate(pool.map(run_one, todo), 1):
            st = rec.get('stability') or {}
            nd = '' if st.get('deterministic', True) else 'NONDET'
            h = (rec.get("head_to_head") or {}).get("outcome", "")
            bad = "" if rec.get("uncertainty", {}).get("correct_behavior", True) else "BEHAVIOR"
            flag = " ".join(x for x in (nd, h if h in ("model_wins",) else "", bad) if x)
            print(f"  [{i:>3}/{len(todo)}] {rec['question']:<19}{rec['site']:<24}{flag}")
            out.append(rec)

    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / ("quick.json" if args.quick else "run.json")
    path.write_text(json.dumps(out, indent=1))
    print(f"\nwrote {path}  ({len(out)} records)")


if __name__ == "__main__":
    main()
