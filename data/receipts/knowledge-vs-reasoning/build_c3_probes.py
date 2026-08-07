#!/usr/bin/env python3
"""C3 — CONTRADICTORY context: gold vs the model's OWN closed-book confabulation.

C1/C2 both hit ceiling, so neither could detect a selection deficit. C3 is built to have teeth:
the reference block contains two entries for the SAME question, one carrying the gold answer and
one carrying the exact wrong answer the pruned model produced closed-book. Nothing in the block
says which is right.

WHY THAT IS A REAL TEST AND NOT A COIN FLIP. The two arms have DIFFERENT priors on these same
items: base answered them correctly closed-book, pruned produced the confabulation. So base is the
control -- if the prior leaks into the choice, base should favour gold and pruned should favour its
own fabrication. Any gap between the arms is prior leakage under contradiction, which is exactly
the failure mode that matters when retrieval returns something the model "disagrees" with.

POSITION BIAS IS MEASURED, NOT ASSUMED. With only two entries, order could dominate the result. So
every item is emitted TWICE -- once gold-first (C3a), once gold-second (C3b). The paired design
cancels position bias in the arm comparison and lets it be reported directly.

Population: the 98 CORRECT->WRONG transitions minus the 5 hand-verified grader artifacts (where
pruned's "wrong" answer was actually right, which would put two correct entries in the block).
"""
import json, re, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

EXCLUDE = {"researcher"}
ARTIFACTS = {"Michael Faraday", "Johannes Kepler", "Wolfgang Pauli", "Warsaw", "East African Rift"}
MAXW = 8          # the confabulation must be a short answer-like span, not a paragraph

# SHAPE PARITY. Both entries must be BARE answers. A first pass put gold "Ottawa" against
# confabulation "The capital of Canada is Toronto" -- the model could then separate them by form
# rather than content and score well for the wrong reason, which would read as robustness. So the
# confabulation is reduced to its answer span by the same conservative rule used in
# build_heal_cases.py, and items where that fails are dropped rather than patched.
BOLD = re.compile(r"\*\*(.+?)\*\*")
CONN = re.compile(r"\b(?:is|are|was|were|by)\s+")
PART = re.compile(r"^(?:founded|written|completed|published|designed|discovered|built|"
                  r"established|sculpted|painted|composed|invented|formulated|launched)\s+"
                  r"(?:in|by|on|at)\s+", re.I)


def bare_answer(resp):
    """-> a bare answer span, or None. Same rule as build_heal_cases.answer_span."""
    resp = resp.strip()
    m = list(BOLD.finditer(resp))
    if len(m) == 1:
        return m[0].group(1).strip()
    if len(resp.split()) <= 3:
        return resp.rstrip(".")                    # already bare
    first = re.split(r"(?<=[.!?])\s", resp)[0].rstrip(".!?")
    ms = list(CONN.finditer(first))
    if not ms:
        return None
    tail = first[ms[-1].end():].strip()
    if not tail or len(tail.split()) > 6:
        return None
    if any(ch in tail for ch in '"\'()*[]'):
        return None
    return PART.sub("", tail).strip() or None


def load(p):
    o = {}
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        if r.get("source_type") in EXCLUDE:
            continue
        o[r["id"]] = r
    return o


def block(q, first, second):
    return (f"Reference material:\n- {q}  {first}\n- {q}  {second}\n\n"
            f"Using only the reference material above, answer:\n{q}")


base, reap = load(sys.argv[1]), load(sys.argv[2])
out, skipped = [], 0
for i in sorted(set(base) & set(reap)):
    b, p = base[i], reap[i]
    if grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))[0] != "CORRECT":
        continue
    if grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))[0] != "WRONG":
        continue
    if b["gold"] in ARTIFACTS:
        continue
    conf = bare_answer(p.get("response") or "")
    gold = str(b["gold"]).split(";")[0].strip()
    # usable only when the confabulation reduces to a bare span of comparable shape to the gold,
    # and does not contain the gold (which would make both entries correct)
    if not conf or len(conf.split()) > MAXW or gold.lower() in conf.lower() \
            or conf.lower() in gold.lower():
        skipped += 1
        continue
    q = b["question"]
    out.append({"id": f"{i}__C3a", "tier": b["tier"], "question": block(q, gold, conf),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})
    out.append({"id": f"{i}__C3b", "tier": b["tier"], "question": block(q, conf, gold),
                "answer": b["gold"], "source_type": b.get("source_type"), "domain": b.get("domain")})

json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
n = len(out) // 2
print(f"usable items: {n}  (skipped {skipped}: confabulation too long, empty, or contains the gold)")
print(f"emitted {len(out)} records ({n} gold-first + {n} gold-second) -> {sys.argv[3]}")
print("\n--- sample C3a ---")
print(out[0]["question"])
print("\n--- same item, C3b ---")
print(out[1]["question"])
