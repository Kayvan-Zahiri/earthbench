"""Axis 1a: the tool-choice layer.

The rest of the benchmark measures Mireye's INTERNAL planner -- which fields
/v1/ask decides to pull. This measures the layer above it: an agent holding the
Mireye MCP server has two tools and must pick one.

The tool descriptions below are copied VERBATIM from mireye_earth_mcp 0.1.0
(server.py, the @mcp.tool docstrings). That matters. If the descriptions were
rewritten for the benchmark, the benchmark would be measuring the rewriter's
prompt engineering rather than Mireye's MCP. These are the exact words a real
agent reads.

TWO THINGS THE DESCRIPTIONS THEMSELVES CREATE

1. mireye_ask's own examples are single-field lookups. "Is this in a flood zone?"
   is fema_flood_zone. The description steers an agent toward the LLM synthesis
   path for questions a raw fetch answers better -- and that path demonstrably
   escalates field errors (see checks/grounding.py: a medium-confidence
   "Unincorporated" becomes the flat assertion "It does not lie within an
   incorporated city", plus an invented "near the Presidio").

2. The MCP exposes exactly two tools, and NEITHER lists the available fields.
   mireye_fetch takes `fields: list[str]` out of a catalogue of 255, and there is
   no discovery tool -- /v1/meta/fields exists on the REST API but is not exposed
   over MCP. So an agent that wants to fetch must GUESS field names. We measure
   how often it guesses wrong.
"""

# Verbatim from mireye_earth_mcp/server.py @mcp.tool() docstrings. Do not edit.
MIREYE_ASK_DESC = (
    "Answer a natural-language question about a US coordinate, with citations to "
    "authoritative federal data sources. Returns the answer plus per-citation "
    "provenance (source, source URL, fetched_at, confidence). Use this when the "
    "caller has a specific question about a place (e.g. 'is this in a flood zone?', "
    "'what's the wildfire risk here?', 'what kind of building is at this address?')."
)

MIREYE_FETCH_DESC = (
    "Fetch specific data fields at a US coordinate with full provenance per field. "
    "Use this when the caller knows exactly which fields they need (e.g. 'elevation "
    "and slope at this point') or wants to power a custom workflow. Each field "
    "includes its value, source, source URL, fetched_at timestamp, and confidence."
)

TOOLS = [
    {
        "name": "mireye_ask",
        "description": MIREYE_ASK_DESC,
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lng": {"type": "number"},
                "question": {"type": "string"},
            },
            "required": ["lat", "lng", "question"],
        },
    },
    {
        "name": "mireye_fetch",
        "description": MIREYE_FETCH_DESC,
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"},
                "lng": {"type": "number"},
                "fields": {"type": "array", "items": {"type": "string"}},
                "preset": {"type": "string"},
            },
            "required": ["lat", "lng"],
        },
    },
]


def score(calls: list[dict], expected_tool: str, catalog: set[str]) -> dict:
    """calls: [{"tool": name, "input": {...}}] in the order the agent made them."""
    used = [c["tool"] for c in calls]

    requested: list[str] = []
    for c in calls:
        if c["tool"] == "mireye_fetch":
            requested += list(c["input"].get("fields") or [])

    hallucinated = [f for f in requested if f not in catalog]

    return {
        "expected_tool": expected_tool,
        "tools_called": used,
        "n_calls": len(calls),
        "first_tool": used[0] if used else None,
        "correct_tool": (used[0] == expected_tool) if used else False,
        "called_both": len(set(used)) > 1,
        # An agent that reaches for /ask when a single named field answers the
        # question has routed itself through the LLM synthesis layer for nothing,
        # and inherited its escalation risk for free.
        "over_asked": expected_tool == "mireye_fetch" and used and used[0] == "mireye_ask",
        "fields_requested": requested,
        "fields_hallucinated": hallucinated,
        "hallucination_rate": (len(hallucinated) / len(requested)) if requested else None,
    }
