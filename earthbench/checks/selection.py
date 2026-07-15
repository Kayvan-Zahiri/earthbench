"""Axis 1: did the planner choose the right fields?

Mireye's /ask runs its own planner ("a planner picks the right fields, fetches
them with provenance, and synthesizes"). It reports what it used in `fields_used`.
So we can score that selection against a gold set.

F1 is the headline number, but it is not the number that matters. DECISIVE RECALL
is. A planner that fetches nine relevant fields and misses the one that determines
the answer has failed, and an F1 of 0.9 will hide that.
"""


def score(fields_used: list[str], gold: set[str], decisive: set[str],
          data_gaps: list | None = None, refused: bool = False) -> dict:
    """
    Two corrections the first version of this got wrong, both of which slandered
    the system under test:

    1. `fields_used` only lists fields that RETURNED A VALUE. A field the planner
       selected that came back null is reported in `data_gaps` instead. Scoring
       selection off `fields_used` alone therefore punishes the planner for the
       DATA being missing, which is not a selection failure at all. Asked whether
       a Zone AE parcel sits above its base flood elevation, Mireye did request
       fema_base_flood_elevation -- FEMA just has no static BFE on that polygon,
       which Mireye then explained correctly. Counting that as a miss was wrong.

    2. When the correct behavior is refusal, there is nothing to select, and
       scoring recall against a gold set punishes the model for doing the right
       thing. Those cases return None and are excluded from the mean.
    """
    used = set(fields_used or [])
    # A field the planner reached for that came back empty was still SELECTED.
    attempted = {g.get("field") for g in (data_gaps or []) if isinstance(g, dict) and g.get("field")}
    selected = used | attempted

    if refused:
        return {"scored": False, "reason": "correct refusal -- nothing to select",
                "precision": None, "recall": None, "f1": None, "decisive_recall": None,
                "n_used": len(used)}

    used = selected

    if not gold:
        # Questions where the correct behavior is to fetch nothing (refusals).
        # Any field pulled here is the planner reaching for a substitute.
        return {
            "precision": None,
            "recall": None,
            "f1": None,
            "decisive_recall": None,
            "n_used": len(used),
            "reached_for_substitute": sorted(used),
        }

    hit = used & gold
    precision = len(hit) / len(used) if used else 0.0
    recall = len(hit) / len(gold)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    dec_hit = used & decisive
    decisive_recall = (len(dec_hit) / len(decisive)) if decisive else None

    return {
        "scored": True,
        "selected_via_data_gaps": sorted(attempted),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "decisive_recall": round(decisive_recall, 3) if decisive_recall is not None else None,
        "missed_decisive": sorted(decisive - used),
        "missed": sorted(gold - used),
        "extra": sorted(used - gold),
        "n_used": len(used),
    }
