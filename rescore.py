"""Re-apply the current correctness rules to a saved run. No network, no API keys.

    python3 rescore.py            # show what would change
    python3 rescore.py --write    # apply it

Why this exists. `checks/correctness.py` was fixed after the 2026-08-05 run to
stop scoring a point as a Mireye error when the live FEMA NFHL oracle returned
nothing for it. The fix landed in the checker but `results/run.json` was never
rebuilt, so the saved records still carried the old scoring: `report.py` printed
`fema_flood_zone 58/68` while the README and the write-up said 58/58. The code
and the artifact disagreed.

Re-running the whole benchmark would fix it, but that is 43 minutes of live API
calls and it would also change every other number, which makes the one
correction impossible to see. So this re-scores the saved records instead.

It changes no observation. `expected` and `got` are read, never written. All it
does is move a record from "Mireye got this wrong" to "there was nothing to
score against", which is the judgement the committed checker already makes.
"""

from __future__ import annotations

import json
import pathlib
import sys

RUN = pathlib.Path("results/run.json")
SKIP_NOTE = "oracle unavailable: FEMA NFHL returned no zone for this point"


def main() -> int:
    write = "--write" in sys.argv
    recs = json.loads(RUN.read_text())
    changed = []

    for r in recs:
        for c in r.get("correctness") or []:
            # The only rule that moved: a flood-zone point with no oracle value
            # cannot be scored, so it is skipped rather than counted as an error.
            if (c.get("field") == "fema_flood_zone"
                    and c.get("correct") is False
                    and not c.get("expected")):
                changed.append((r["key"], c.get("got")))
                if write:
                    c["correct"] = None
                    c["skipped"] = SKIP_NOTE

    print(f"  {len(changed)} record(s) move from error to skipped:")
    for key, got in changed:
        print(f"    {key:<34} mireye said {got!r}, oracle returned nothing")

    if not write:
        print("\n  dry run. Re-run with --write to apply.")
        return 0

    RUN.write_text(json.dumps(recs, indent=1))
    print(f"\n  wrote {RUN}. Regenerate ALL_ANSWERS.md next:")
    print("    python3 make_all_answers.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
