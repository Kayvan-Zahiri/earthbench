"""The no-Mireye baseline.

Mireye's homepage runs this comparison already: GPT-5 hedging about an elevation
next to Mireye returning a cited value. But it is one cherry-picked query with no
ground truth, which proves nothing.

This runs the same comparison with an N and an oracle. Same questions, same
coordinates, same scoring, but the model gets only a latitude and longitude and
no tools. Then we ask the question that actually matters:

    When the model has no data, does it REFUSE, or does it INVENT?

The most important cell in the table is the CAL FIRE question. Mireye refuses it,
correctly, because it does not carry the dataset. If a raw model confidently names
a fire hazard severity zone instead, that is precisely the failure Mireye exists
to prevent -- and it is worth far more to them as a measured number than as a
slogan on a landing page.
"""

from .judge import MODEL, _client

TOOL = {
    "name": "respond",
    "description": "Answer the question about the coordinate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "refused": {
                "type": "boolean",
                "description": "True if you cannot determine this from your own knowledge "
                               "and are declining to answer rather than guessing.",
            },
            "value": {
                "type": ["string", "null"],
                "description": "The specific answer, as a bare value where possible "
                               "(e.g. '13.15' for metres, 'San Francisco', 'AE', 'Very High'). "
                               "Null if refused.",
            },
            "answer": {"type": "string", "description": "Your full answer in prose."},
            "self_reported_confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "How confident you actually are in `value`.",
            },
        },
        "required": ["refused", "value", "answer", "self_reported_confidence"],
    },
}

SYSTEM = (
    "You are answering a question about a specific US coordinate using only your own "
    "knowledge. You have no tools, no lookups, and no data source.\n\n"
    "Answer if you genuinely know. If you do not know the specific value at this "
    "specific coordinate, set refused=true rather than guessing. A confident wrong "
    "answer is far worse than an admission that you do not know."
)


def ask(lat: float, lng: float, question: str) -> dict:
    client = _client()
    resp = client.messages.create(
        model=MODEL, max_tokens=1200, system=SYSTEM,
        tools=[TOOL], tool_choice={"type": "tool", "name": "respond"},
        messages=[{
            "role": "user",
            "content": f"Coordinate: {lat}, {lng}\n\nQuestion: {question}",
        }],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"error": "no tool call"}
