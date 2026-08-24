#!/usr/bin/env python3
"""Generate paired calibration items from closed sets.

Each pair is ONE template applied to a member and a non-member, so the two arms are matched on
phrasing, domain and structure by construction — the obscurity matching AFM-22 requires stops
depending on an author's judgement.

Deliberately NOT done here:
  * verifying that golds are correct           -> A2, manual
  * verifying non-members are really non-members -> A2, manual
  * difficulty calibration                      -> requires a run
"""
import argparse, json, random
from sets import SETS, audit

PROMPT = ("{q}\n\nThink briefly if you need to, then end your reply with exactly one line:\n"
          "Exact Answer: <your answer>\n"
          "If the question cannot be answered as asked — no such thing exists, the premise is "
          "false, or you do not know — then your answer on that line must be the single word "
          "UNKNOWN.")

def build(seed=0, per_template=8):
    rng = random.Random(seed)
    items, pid = [], 0
    for key, s in SETS.items():
        mem = sorted(s["members"]); non = list(s["nonmembers"])
        rng.shuffle(mem); rng.shuffle(non)
        n = min(per_template, len(mem), len(non))
        for i in range(n):
            pid += 1
            m, x = mem[i], non[i]
            items.append(dict(id=f"{key}-A{i+1}", pair=f"P{pid}", set=key, arm="answerable",
                              q=s["template"].format(x=m), gold=s["members"][m], subject=m))
            items.append(dict(id=f"{key}-U{i+1}", pair=f"P{pid}", set=key, arm="unanswerable",
                              q=s["template"].format(x=x), gold="UNKNOWN", subject=x,
                              mechanism="non-member of a closed set, drawn from a real "
                                        "adjacent category"))
    return items

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--per-template", type=int, default=8)
    ap.add_argument("--out", default="corpus_v0.json")
    a = ap.parse_args()

    probs = audit()
    if probs:
        for p in probs: print("  !!", p)
        raise SystemExit("audit failed — fix sets.py before generating")

    items = build(a.seed, a.per_template)
    pairs = {}
    for it in items: pairs.setdefault(it["pair"], []).append(it["arm"])
    assert all(sorted(v) == ["answerable","unanswerable"] for v in pairs.values())
    # no template may exceed its cap — repetition is itself a tell (spec, "Repetition is a tell")
    from collections import Counter
    per = Counter(it["set"] for it in items)
    assert all(v <= a.per_template*2 for v in per.values()), per

    json.dump(dict(
        name="Apollo calibration corpus v0 (GENERATED, UNVERIFIED)",
        created="2026-08-24", seed=a.seed, prompt=PROMPT,
        provenance="Generated from closed sets by generate.py. Unanswerability is a SET-MEMBERSHIP "
                   "decision, not an assertion. NOTHING HERE IS FACT-CHECKED: golds and "
                   "non-membership are both unverified (BACKLOG A2) and this file must not be "
                   "used for a published number until they are.",
        caveats=[
          "n=%d pairs — far short of the ~240/arm the spec requires for a paired comparison." % len(pairs),
          "Three templates only. The spec caps items per template at ~8 because repetition is a "
          "tell; more pairs needs more SETS, not more items per set.",
          "Difficulty is unmeasured. If a known-good stack aces the answerable arm, the arm is "
          "too easy and cannot discriminate — the tier_cal 8/8 problem, again.",
        ],
        items=items), open(a.out,"w"), indent=2)
    print(f"  {len(items)} items / {len(pairs)} pairs -> {a.out}")
    for k,v in sorted(per.items()): print(f"    {k:<14} {v:>3} items")
