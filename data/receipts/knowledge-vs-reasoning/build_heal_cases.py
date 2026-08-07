#!/usr/bin/env python3
"""Build the P-HEAL case list from the two committed runs. Deterministic; no sampling RNG.

arm="wrong"   : the 77 CORRECT->WRONG cases whose response shares NOTHING with the gold
                (ERROR_STRUCTURE_AND_HEALING.md §3) -- 5 hand-verified grader artifacts excluded.
arm="refusal" : a deterministic 60-case sample of the 260 CORRECT->REFUSAL cases (§1), taken by
                even stride over id-sorted order so it cannot be tuned to the result.

emitted_answer is the span measure (B) truncates before. It is filled ONLY when the answer is
unambiguously locatable; otherwise None and that case contributes to measure A alone. Three
accepted patterns, in order:
    **bolded**                   -> the bolded span
    "... is <X>." / "... by <X>." -> the tail after the LAST such connective
    (bare short answer)          -> no slot; truncating would leave an empty prefix, which is
                                    measure A by another name
"""
import json, re, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade, norm

EXCLUDE = {"researcher"}
ARTIFACTS = {"Michael Faraday", "Johannes Kepler", "Wolfgang Pauli", "Warsaw", "East African Rift"}
STOP = {"the", "a", "an", "of", "in", "is", "was", "by", "and", "de", "la", "von", "who", "mount",
        "river", "city", "island", "first", "written", "also", "known", "as", "it", "for", "to",
        "at", "on", "that", "with", "year", "name", "largest", "highest", "lake", "desert",
        "tunnel", "reef"}
BOLD = re.compile(r"\*\*(.+?)\*\*")
CONN = re.compile(r"\b(?:is|are|was|were|by)\s+")
# a leading participle is scaffolding, not the answer: "was founded in 1949" -> "1949".
# Adding "in" to CONN instead was tried and is WRONG -- it takes the trailing locative, turning
# "...is the island of K2, located in Pakistan" into "Pakistan" and losing the actual claim.
PART = re.compile(r"^(?:founded|written|completed|published|designed|discovered|built|"
                  r"established|sculpted|painted|composed|invented|formulated|launched)\s+"
                  r"(?:in|by|on|at)\s+", re.I)


def tk(s):
    return [t for t in norm(s).split() if t not in STOP and len(t) > 2]


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


def answer_span(resp):
    """Conservative. Rejecting a case costs one data point; mislocating one corrupts a measurement.

    Restricted to the FIRST sentence -- taking the last connective across a multi-sentence reply
    picked 'launched on July 29, 1958' out of the Sputnik answer and '4,000 meters (13,123 feet)
    high' out of the Everest answer, i.e. an incidental clause rather than the claim. The span must
    also run to the end of that sentence, so a mid-sentence fragment like '"S-56")' cannot qualify.
    """
    m = list(BOLD.finditer(resp))
    if len(m) == 1:
        return m[0].group(1).strip()
    if len(resp.split()) <= 3:
        return None                       # bare answer: no slot to truncate at
    first = re.split(r"(?<=[.!?])\s", resp.strip())[0].rstrip(".!?")
    ms = list(CONN.finditer(first))
    if not ms:
        return None
    tail = first[ms[-1].end():].strip()
    if not tail or len(tail.split()) > 6:
        return None
    if any(ch in tail for ch in '"\'()*[]'):
        return None                       # unbalanced fragment, not a clean entity
    tail = PART.sub("", tail).strip()
    return tail or None


base, reap = load(sys.argv[1]), load(sys.argv[2])
cases, n_wrong_slot = [], 0

for i in sorted(set(base) & set(reap)):
    b, p = base[i], reap[i]
    if grade(b["gold"], b.get("response", ""), 25, b.get("finish_reason"))[0] != "CORRECT":
        continue
    vp = grade(p["gold"], p.get("response", ""), 25, p.get("finish_reason"))[0]
    resp = (p.get("response") or "").strip()

    if vp == "WRONG" and b["gold"] not in ARTIFACTS:
        gt, rn = tk(b["gold"]), norm(resp)
        rw = rn.split()
        hit = any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", rn) for t in gt) or \
              any(3 <= len(w) < len(g) and g.startswith(w) for g in gt for w in rw)
        if hit:
            continue                       # retains residual signal; not the population under test
        span = answer_span(resp)
        if span:
            n_wrong_slot += 1
        cases.append({"id": i, "arm": "wrong", "tier": b["tier"], "question": b["question"],
                      "gold": b["gold"], "emitted": resp, "emitted_answer": span})

    elif vp == "REFUSAL":
        cases.append({"id": i, "arm": "refusal", "tier": b["tier"], "question": b["question"],
                      "gold": b["gold"], "emitted": resp, "emitted_answer": None})

wrong = [c for c in cases if c["arm"] == "wrong"]
refus = [c for c in cases if c["arm"] == "refusal"]
stride = max(1, len(refus) // 60)
refus_s = refus[::stride][:60]

print(f"arm=wrong   : {len(wrong)} cases; {n_wrong_slot} admit an unambiguous answer slot "
      f"({n_wrong_slot/max(len(wrong),1):.0%}) -> measure B runs on those only")
print(f"arm=refusal : {len(refus)} total, sampled {len(refus_s)} at stride {stride}")
json.dump(wrong + refus_s, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
print(f"-> {sys.argv[3]}")
