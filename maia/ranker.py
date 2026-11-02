"""Update on evidence, not on pressure (DESIGN.md rule 6).

A pure function. The action (hold / concede / ask) depends only on what the claim rests on, whether the challenger
brought anything new, and Maia's confidence. The cost of being wrong is deliberately NOT an input to the action: it sets
`firmness`, how hard she argues while holding or asking. A costly mistake makes her argue harder, never makes her
immune to evidence -- that is how a confident agent stays wrong for days.
"""
from __future__ import annotations

from dataclasses import dataclass

EVIDENCE = ("receipt", "commit", "correction", "inferred")
# Claims resting on something checkable. The person's own correction counts: un-correcting it needs a new correction.
GROUNDED = {"receipt", "commit", "correction"}
LOW_CONFIDENCE = 0.5

HOLD, CONCEDE, ASK = "hold", "concede", "ask"


@dataclass(frozen=True)
class Stance:
    action: str
    firmness: float  # 0..1, how hard to argue; 0 when conceding
    reason: str


def decide(evidence: str, new_evidence: bool, confidence: float, cost_of_wrong: float) -> Stance:
    if evidence not in EVIDENCE:
        raise ValueError(f"evidence must be one of {EVIDENCE}")
    if not (0 <= confidence <= 1 and 0 <= cost_of_wrong <= 1):
        raise ValueError("confidence and cost_of_wrong are in 0..1")

    grounded = evidence in GROUNDED
    low = confidence < LOW_CONFIDENCE

    if new_evidence:
        if grounded and not low:
            # Two pieces of evidence disagree; neither wins by assertion. Ask to see it and compare.
            action, reason = ASK, "new evidence against a grounded claim: compare the two"
        else:
            action, reason = CONCEDE, "new evidence beats an inference or a low-confidence claim"
    elif grounded:
        # Pressure is not evidence. Low confidence does not lower a receipt: the receipt is what she is confident in.
        action, reason = HOLD, f"claim rests on a {evidence} and nothing new was offered"
    elif low:
        action, reason = CONCEDE, "inferred and unsure: concede on the first pushback"
    else:
        # An inference she believes, but cannot point at: ask what the person knows rather than dig in.
        action, reason = ASK, "inferred but confident: ask what the person knows"

    firmness = 0.0 if action == CONCEDE else round(cost_of_wrong, 3)
    return Stance(action, firmness, reason)
