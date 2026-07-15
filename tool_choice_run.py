"""Run the tool-choice axis.

    python3 tool_choice_run.py

An agent is handed Mireye's two MCP tools -- with their VERBATIM descriptions --
and the questions from the benchmark. It is told nothing else. Tool calls are
executed for real against Mireye, so the agent sees genuine results and can
recover from a bad call, exactly as it would in production.

What we measure:

  tool choice      does it reach for ask or fetch, and is that the right call
  over-ask         does it route a single-field lookup through the LLM synthesis
                   path, inheriting its escalation risk for no benefit
  hallucinated     mireye_fetch takes field names out of a 255-field catalogue and
  field names      the MCP exposes NO way to discover them. So the agent guesses.
                   How often is the guess not a real field?
"""

import json
import pathlib
import urllib.request

from earthbench import mireye
from earthbench.checks import tool_choice
from earthbench.fixtures.questions import BY_ID as QUESTIONS
from earthbench.fixtures.sites import BY_ID as SITES
from earthbench.judge import MODEL, _client

# What a competent agent should reach for first.
#   fetch : the question names a value that maps to one or two known fields
#   ask   : open-ended, needs the planner to choose fields and synthesize
EXPECTED = {
    "elevation": "mireye_fetch",
    "locality": "mireye_fetch",
    "flood_zone": "mireye_fetch",
    "bfe_margin": "mireye_fetch",
    "wildfire_synthesis": "mireye_ask",
    "post_fire_fuel": "mireye_ask",
    "fhsz": "mireye_ask",
}

CASES = [
    ("elevation", "sf_marina"), ("elevation", "paradise"),
    ("locality", "sf_marina"), ("locality", "denver"), ("locality", "manhattan"),
    ("flood_zone", "guerneville"), ("flood_zone", "sf_marina"),
    ("bfe_margin", "guerneville"),
    ("wildfire_synthesis", "oakland_hills_high"), ("wildfire_synthesis", "paradise"),
    ("post_fire_fuel", "paradise"),
    ("fhsz", "oakland_hills_high"),
]

SYSTEM = (
    "You are an agent with access to the Mireye Earth MCP server. Answer the user's "
    "question about the given coordinate using the tools available to you. "
    "Use the tools; do not answer from your own knowledge."
)


def catalog() -> set[str]:
    with urllib.request.urlopen("https://api.mireye.com/v1/meta/fields", timeout=30) as r:
        return {f["name"] for f in json.loads(r.read())["fields"]}


def execute(name: str, args: dict) -> dict:
    if name == "mireye_ask":
        return mireye.ask(args["lat"], args["lng"], args["question"])
    return {"fields": mireye.fetch(args["lat"], args["lng"], args.get("fields"))}


def run_case(qid: str, sid: str, fields: set[str]) -> dict:
    q, s = QUESTIONS[qid], SITES[sid]
    client = _client()

    messages = [{"role": "user", "content": f"Coordinate: {s.lat}, {s.lng}\n\n{q.text}"}]
    calls: list[dict] = []

    for _ in range(4):   # let it recover from a bad call, like it could in production
        resp = client.messages.create(
            model=MODEL, max_tokens=2000, system=SYSTEM,
            tools=tool_choice.TOOLS, messages=messages,
        )
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if not tool_uses:
            break

        # Rebuild the assistant turn as plain dicts; handing the SDK its own
        # block objects back trips a pydantic serialization path.
        assistant = []
        for b in resp.content:
            if b.type == "text":
                assistant.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                assistant.append({"type": "tool_use", "id": b.id,
                                  "name": b.name, "input": b.input})
        messages.append({"role": "assistant", "content": assistant})
        results = []
        for tu in tool_uses:
            calls.append({"tool": tu.name, "input": tu.input})
            try:
                out = execute(tu.name, tu.input)
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": json.dumps(out)[:4000]})
            except Exception as exc:
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": f"error: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})

    rec = tool_choice.score(calls, EXPECTED[qid], fields)
    rec.update({"key": f"{qid}@{sid}", "question": qid, "site": sid})
    return rec


def main() -> None:
    fields = catalog()
    print(f"field catalogue: {len(fields)} names (NOT discoverable through the MCP)\n")

    out = []
    for qid, sid in CASES:
        rec = run_case(qid, sid, fields)
        flag = []
        if rec["over_asked"]:
            flag.append("OVER-ASK")
        if rec["fields_hallucinated"]:
            flag.append(f"HALLUCINATED {rec['fields_hallucinated']}")
        print(f"  {rec['key']:<32} want={rec['expected_tool']:<13} "
              f"got={str(rec['first_tool']):<13} {' '.join(flag)}")
        out.append(rec)

    pathlib.Path("results").mkdir(exist_ok=True)
    pathlib.Path("results/tool_choice.json").write_text(json.dumps(out, indent=1))

    n = len(out)
    correct = sum(r["correct_tool"] for r in out)
    over = sum(r["over_asked"] for r in out)
    req = [f for r in out for f in r["fields_requested"]]
    bad = [f for r in out for f in r["fields_hallucinated"]]

    print(f"\n  correct first tool     {correct}/{n}")
    print(f"  over-asked             {over}/{sum(1 for r in out if r['expected_tool']=='mireye_fetch')}"
          f"   (single-field lookups routed through the LLM path)")
    print(f"  field names requested  {len(req)}")
    print(f"  not real fields        {len(bad)}"
          f"  ({100*len(bad)/len(req):.0f}%)" if req else "")
    if bad:
        print(f"    hallucinated: {sorted(set(bad))}")


if __name__ == "__main__":
    main()
