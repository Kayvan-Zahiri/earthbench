"""The LLM judge, and the reason it is not trusted on its own.

The deterministic checks catch blatant failures. Semantic ones need judgment: is
"1% annual chance floodplain" a claim about this site or a definition of the
term? A regex cannot tell. A model can.

But an unvalidated judge is a vibe with a spreadsheet. So judge.py is always run
alongside label.py, which collects human labels on a sample, and validate() reports
how often the judge agrees with the human. If that agreement is poor, the judged
numbers in the report do not get to be quoted. That is the whole contract.
"""

import json
import os
import pathlib

import anthropic

MODEL = "claude-opus-4-8"

SYSTEM = """You are grading a geospatial API's natural-language answer.

You will be given: the question, the answer the API produced, and the EXACT field
values the API says it used (with their source, unit, and confidence).

Grade only what is in front of you. You are NOT judging whether the field values
are true about the world -- that is measured separately against outside authorities.
You are judging whether the ANSWER follows from the FIELDS.

Be strict about three things:

1. UNSUPPORTED CLAIMS. Any assertion about this location that no cited field
   supports. Geographic colour ("near the Presidio"), causal reasoning, or a
   number that cannot be derived from a field value. Restating a definition
   ("Zone X is outside the 1% annual chance floodplain") is NOT an unsupported
   claim. Inventing a fact about this site IS.

2. ESCALATION. The answer stating something MORE strongly than the field warrants.
   A field with confidence "medium" restated as flat fact. An ambiguous field
   value elaborated into a confident conclusion. This is the failure that matters
   most: it means the LLM layer amplifies data error rather than damping it.

3. PRECISION. Reporting more significant figures than the source supports, with
   no error bar. Elevation from a 10m DEM (about 1m vertical RMSE) stated to the
   centimetre is overstated precision.

Also report whether the answer HEDGES: does it communicate the limits of what it
knows -- coarse resolution, medium confidence, "verify with a professional",
"this is not the authoritative map"?"""

TOOL = {
    "name": "grade",
    "description": "Report the grading result.",
    "input_schema": {
        "type": "object",
        "properties": {
            "faithful": {"type": "boolean",
                         "description": "Every claim about this site is supported by a cited field."},
            "unsupported_claims": {"type": "array", "items": {"type": "string"},
                                   "description": "Verbatim claims not supported by any cited field."},
            "escalated": {"type": "boolean",
                          "description": "The answer states something more strongly than the field warrants."},
            "escalation_detail": {"type": "string"},
            "overstated_precision": {"type": "boolean"},
            "hedged": {"type": "boolean",
                       "description": "The answer communicates the limits of what it knows."},
            "reasoning": {"type": "string"},
        },
        "required": ["faithful", "unsupported_claims", "escalated", "overstated_precision",
                     "hedged", "reasoning"],
    },
}


def _client():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        for c in (pathlib.Path(".env"), pathlib.Path.home() / "Desktop/jobs/.env"):
            if c.exists():
                for line in c.read_text().splitlines():
                    if line.strip().startswith("ANTHROPIC_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip("\"'")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key)


def _fields_block(fetched: dict) -> str:
    lines = []
    for name, f in sorted(fetched.items()):
        lines.append(
            f"  {name} = {f.get('value')!r} {f.get('unit') or ''}".rstrip()
            + f"\n      source={f.get('source')} confidence={f.get('confidence')} status={f.get('status')}"
            + (f"\n      notes={f.get('notes')}" if f.get("notes") else "")
        )
    return "\n".join(lines) or "  (no fields cited)"


def grade(question: str, answer: str, fetched: dict) -> dict:
    client = _client()
    prompt = (
        f"QUESTION\n  {question}\n\n"
        f"FIELDS THE API SAYS IT USED\n{_fields_block(fetched)}\n\n"
        f"THE ANSWER IT PRODUCED\n  {answer}"
    )
    resp = client.messages.create(
        model=MODEL, max_tokens=1500, system=SYSTEM,
        tools=[TOOL], tool_choice={"type": "tool", "name": "grade"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"error": "judge did not call the tool"}


def validate(judged: list[dict], labeled: list[dict]) -> dict:
    """Does the judge agree with the human?

    labeled: [{"key": "<question>@<site>", "faithful": bool, "escalated": bool, ...}]

    If agreement here is weak, the judged numbers in the report are not quotable,
    and the report says so instead of quietly reporting them anyway.
    """
    by_key = {j["key"]: j for j in judged}
    fields = ["faithful", "escalated", "overstated_precision", "hedged"]
    out = {}
    for f in fields:
        pairs = [(by_key[l["key"]].get(f), l.get(f))
                 for l in labeled if l["key"] in by_key and f in l]
        if not pairs:
            continue
        agree = sum(1 for a, b in pairs if a == b)
        out[f] = {
            "n": len(pairs),
            "agreement": round(agree / len(pairs), 3),
            "disagreements": [k["key"] for k in labeled
                              if k["key"] in by_key and f in k
                              and by_key[k["key"]].get(f) != k.get(f)],
        }
    return out
