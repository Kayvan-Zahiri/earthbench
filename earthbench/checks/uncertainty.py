"""Axis 3: does it know what it does not know?

Most of this needs no LLM judge. Mireye's own response structure says whether it
refused: a refusal comes back with empty `fields_used`, empty `citations`, and
confidence "low". That is a deterministic signal and we use it.

Hedging is softer, so we compute a cheap lexical signal here AND send the same
response to the judge, then report where the two disagree. A benchmark whose only
scorer is an LLM is a vibe with a spreadsheet.
"""

import re

# Language that qualifies an answer rather than asserting it.
HEDGE_MARKERS = [
    r"\bhowever\b", r"\bbut\b", r"\bnote that\b", r"\bkeep in mind\b",
    r"\bapproximate", r"\bestimate", r"\broughly\b", r"\baround\b",
    r"\bmay not\b", r"\bmight not\b", r"\bcannot\b", r"\bcan'?t\b",
    r"\bdoes not\b", r"\bdoesn'?t\b", r"\bnot the\b", r"\buncertain",
    r"\bcoarse\b", r"\bcensus[- ]tract\b", r"\btract[- ]level\b",
    r"\bconsult\b", r"\bverify\b", r"\bprofessional\b", r"\bsurvey",
    r"\bconfidence\b", r"\blimitation", r"\bcaveat", r"±",
]


def behavior(resp: dict) -> str:
    """Deterministic: did it answer or refuse? Read from the response envelope."""
    used = resp.get("fields_used") or []
    cites = resp.get("citations") or []
    conf = (resp.get("confidence") or "").lower()

    if not used and not cites and conf == "low":
        return "refuse"
    return "answer"


def hedged_lexical(resp: dict) -> bool:
    text = (resp.get("answer") or "").lower()
    return any(re.search(p, text) for p in HEDGE_MARKERS)


def data_gaps_populated(resp: dict) -> bool:
    """They ship a machine-readable `data_gaps` field. Does it ever fire?

    This matters more than it looks. An agent consuming this API cannot read prose.
    If the gap is only expressed in the answer text and `data_gaps` stays empty,
    the agent has no programmatic way to learn that something was missing.
    """
    return bool(resp.get("data_gaps"))


def score(resp: dict, expect: str) -> dict:
    got = behavior(resp)

    # expect="hedge" and expect="answer" both require an answer; they differ in
    # whether the answer must be qualified. expect="decline" is a refusal that is
    # correct for a structural reason rather than a missing-data reason.
    should_answer = expect in ("answer", "hedge")
    should_refuse = expect in ("refuse", "decline")

    return {
        "expected": expect,
        "behavior": got,
        "correct_behavior": (got == "answer") if should_answer else (got == "refuse"),
        "false_refusal": should_answer and got == "refuse",
        "false_answer": should_refuse and got == "answer",
        "hedged_lexical": hedged_lexical(resp),
        "hedge_required": expect == "hedge",
        "confidence": resp.get("confidence"),
        "data_gaps_populated": data_gaps_populated(resp),
        "n_citations": len(resp.get("citations") or []),
    }
