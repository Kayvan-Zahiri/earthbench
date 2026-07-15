"""Hand-label a sample so the judge can be validated.

    python3 label.py --n 15        # label a random sample
    python3 label.py --check       # score the judge against your labels

This exists because a benchmark whose only scorer is an LLM is a vibe with a
spreadsheet. You label a sample yourself, blind to the judge's verdict, and then
judge.validate() reports how often the judge agreed with you. If agreement is
poor, the judged numbers in the report do not get quoted -- the report says the
judge was unreliable and falls back to the deterministic checks.

Your labels are the ground truth for the judge. The judge is not ground truth for
anything.
"""

import argparse
import json
import pathlib
import random
import textwrap

from earthbench import judge

RUN = pathlib.Path("results/run.json")
LABELS = pathlib.Path("results/human_labels.json")

PROMPTS = [
    ("faithful",
     "Is EVERY claim about this location supported by a cited field?\n"
     "  (Restating a definition is fine. Inventing a fact about this site is not.)"),
    ("escalated",
     "Does the answer state something MORE strongly than the field warrants?\n"
     "  (e.g. a 'medium' confidence value restated as flat fact)"),
    ("overstated_precision",
     "Does it report more precision than the source can support (no error bar)?"),
    ("hedged",
     "Does the answer communicate the limits of what it knows?"),
]


def ask_bool(prompt: str) -> bool | None:
    while True:
        r = input(f"  {prompt}\n  [y/n/s=skip] > ").strip().lower()
        if r in ("y", "yes"):
            return True
        if r in ("n", "no"):
            return False
        if r in ("s", "skip", ""):
            return None


def label(n: int, seed: int):
    recs = [r for r in json.loads(RUN.read_text())
            if r.get("answer") and r.get("fields_used")]
    random.Random(seed).shuffle(recs)
    existing = json.loads(LABELS.read_text()) if LABELS.exists() else []
    done = {l["key"] for l in existing}
    # Exclude any record already labeled in an earlier pass: once you've seen the
    # judge's verdict for a record, re-labeling it isn't a blind test. Keeps the
    # validation set disjoint from the learning pass.
    for prior in pathlib.Path("results").glob("human_labels_pass*.json"):
        done |= {l["key"] for l in json.loads(prior.read_text())}

    todo = [r for r in recs if r["key"] not in done][:n]
    print(f"labeling {len(todo)} records. the judge's verdict is HIDDEN from you.\n")

    for i, r in enumerate(todo, 1):
        print("=" * 78)
        print(f"[{i}/{len(todo)}]  {r['key']}\n")
        print("FIELDS USED:", ", ".join(r["fields_used"]))
        print("\nANSWER:")
        print(textwrap.indent(textwrap.fill(r["answer"], 74), "  "))
        print()
        entry = {"key": r["key"]}
        for field, prompt in PROMPTS:
            v = ask_bool(prompt)
            if v is not None:
                entry[field] = v
        existing.append(entry)
        LABELS.write_text(json.dumps(existing, indent=1))
        print(f"  saved ({len(existing)} total)\n")


def check():
    recs = json.loads(RUN.read_text())
    judged = [{"key": r["key"], **(r.get("judge") or {})}
              for r in recs if isinstance(r.get("judge"), dict) and "error" not in r["judge"]]
    labeled = json.loads(LABELS.read_text()) if LABELS.exists() else []
    if not labeled:
        print("no human labels yet. run: python3 label.py --n 15")
        return

    agreement = judge.validate(judged, labeled)
    print(f"judge vs human, n_labeled={len(labeled)}\n")
    for field, r in agreement.items():
        verdict = "USABLE" if r["agreement"] >= 0.8 else "NOT TRUSTWORTHY"
        print(f"  {field:22} agreement={r['agreement']:<6} n={r['n']:<4} {verdict}")
        if r["disagreements"]:
            print(f"    disagreed on: {', '.join(r['disagreements'][:6])}")
    print("\nAny axis below 0.8 does not get quoted as a number in the write-up.")
    (pathlib.Path("results") / "judge_validation.json").write_text(json.dumps(agreement, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    check() if a.check else label(a.n, a.seed)
