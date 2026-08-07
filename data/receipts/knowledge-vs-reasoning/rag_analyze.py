#!/usr/bin/env python3
"""Score the RAG arm against PREREG_RAG_ARM.md. Reuses ikp_score.grade unchanged.

Reports per condition per arm: raw accuracy, refusals, and no_answer (G-5). The closed-book
accuracy of the pruned arm on the C1/C2 population is 0% BY CONSTRUCTION -- the population is
exactly the probes it lost -- so every point above zero is recovery.
"""
import json, sys
from collections import defaultdict
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade


def load(p, lab):
    out = defaultdict(list)
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        cond = r["id"].rsplit("__", 1)[1]
        v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
        out[cond].append(v)
    return out


arms = {}
for path, lab in ((sys.argv[1], "base"), (sys.argv[2], "pruned")):
    try:
        arms[lab] = load(path, lab)
    except FileNotFoundError:
        print(f"[rag] {lab}: {path} not present yet")

hdr = f"{'arm':<8}{'cond':<6}{'n':>5}{'correct':>9}{'wrong':>7}{'refus':>7}{'noans':>7}{'acc':>9}"
print(hdr); print("-" * len(hdr))
acc = {}
for lab in ("base", "pruned"):
    if lab not in arms:
        continue
    for cond in ("C1", "C2", "CTRL"):
        vs = arms[lab].get(cond, [])
        if not vs:
            continue
        n = len(vs)
        c = vs.count("CORRECT"); w = vs.count("WRONG")
        rf = vs.count("REFUSAL"); na = vs.count("NO_ANSWER")
        acc[(lab, cond)] = c / n
        print(f"{lab:<8}{cond:<6}{n:>5}{c:>9}{w:>7}{rf:>7}{na:>7}{c/n:>8.1%}")
    print("-" * len(hdr))

if all(k in acc for k in (("base", "C1"), ("pruned", "C1"), ("base", "C2"), ("pruned", "C2"))):
    print("\n=== PREDICTION SCORING (PREREG_RAG_ARM.md §8) ===")
    p1 = acc[("pruned", "C1")]
    print(f"  P-RAG1  pruned C1 >= 90%           : {p1:.1%}  -> "
          f"{'HELD' if p1 >= 0.90 else 'FALSIFIED'}")
    gap = acc[("pruned", "C2")] - acc[("base", "C2")]
    print(f"  P-RAG2  pruned C2 within 10pp base : pruned {acc[('pruned','C2')]:.1%} vs base "
          f"{acc[('base','C2')]:.1%}, gap {gap:+.1f}pp -> "
          f"{'HELD' if abs(gap) <= 0.10 else 'FALSIFIED'}")
    if ("pruned", "CTRL") in acc:
        p3 = acc[("pruned", "CTRL")]
        print(f"  P-RAG3  pruned CTRL >= 90%         : {p3:.1%}  -> "
              f"{'HELD' if p3 >= 0.90 else 'FALSIFIED'}")
    print(f"\n  interference cost (C1 -> C2): base {acc[('base','C2')]-acc[('base','C1')]:+.1%}, "
          f"pruned {acc[('pruned','C2')]-acc[('pruned','C1')]:+.1%}")
    print("  NOTE: closed-book pruned accuracy on the C1/C2 population is 0% by construction.")
