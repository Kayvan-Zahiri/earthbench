#!/bin/bash
# Run the whole benchmark and regenerate both documents.
#
#   ./run_all.sh              full run
#   ./run_all.sh --quick      smoke test, one site per question
#   ./run_all.sh --no-judge   deterministic only, no ANTHROPIC_API_KEY needed
#
# Needs MIREYE_API_KEY in .env. ANTHROPIC_API_KEY is only for the judge and the
# no-data baseline. Oracles (CAL FIRE, CGS, FEMA, USGS) are free and keyless.

set -e
cd "$(dirname "$0")"

echo "==> benchmark"
python3 run.py "$@"

echo "==> MCP tool-choice axis"
python3 tool_choice_run.py

echo "==> summary"
python3 report.py

echo "==> ALL_ANSWERS.md"
python3 make_all_answers.py

echo
echo "Done. results/run.json, results/tool_choice.json, ALL_ANSWERS.md"
echo "Numbers in FULL_REPORT.md are hand-written - recheck them against the summary above."
