#!/usr/bin/env python3
"""Score C3 against PREREG_C3_CONTRADICTION.md. Gold-rate = fraction choosing the gold entry."""
import json, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

def load(p):
    d = {"C3a": [], "C3b": []}
    for l in open(p):
        l = l.strip()
        if not l: continue
        r = json.loads(l)
        cond = r["id"].rsplit("__", 1)[1]
        v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
        d[cond].append((r["id"], v, (r.get("response") or "").strip()))
    return d

A = {"base": load(sys.argv[1]), "pruned": load(sys.argv[2])}
hdr = f"{'arm':<8}{'order':<8}{'n':>5}{'gold':>7}{'confab':>8}{'other':>7}{'gold-rate':>11}"
print(hdr); print("-" * len(hdr))
rate = {}
for lab in ("base", "pruned"):
    tot_g = tot_n = 0
    for cond in ("C3a", "C3b"):
        v = A[lab][cond]
        g = sum(1 for _, x, _ in v if x == "CORRECT")
        w = sum(1 for _, x, _ in v if x == "WRONG")
        o = len(v) - g - w
        rate[(lab, cond)] = g / len(v)
        tot_g += g; tot_n += len(v)
        print(f"{lab:<8}{'gold 1st' if cond=='C3a' else 'gold 2nd':<8}{len(v):>5}{g:>7}{w:>8}{o:>7}{g/len(v):>10.1%}")
    rate[(lab, "ALL")] = tot_g / tot_n
    print(f"{lab:<8}{'POOLED':<8}{tot_n:>5}{tot_g:>7}{'':>8}{'':>7}{tot_g/tot_n:>10.1%}")
    print("-" * len(hdr))

print("\n=== PREDICTION SCORING (PREREG_C3_CONTRADICTION.md §8) ===")
b, p = rate[("base", "ALL")], rate[("pruned", "ALL")]
gate = b >= 0.70
print(f"  P-RAG6  GATE base gold-rate >=70%    : {b:.1%} -> {'HELD' if gate else 'FAILED'}")
pos_b = abs(rate[("base","C3a")] - rate[("base","C3b")])
print(f"  P-RAG5  base position bias <=20pp    : {pos_b*100:.1f}pp -> {'HELD' if pos_b<=0.20 else 'FALSIFIED'}")
gap = b - p
if gate:
    print(f"  P-RAG4  pruned >=15pp BELOW base     : base {b:.1%} vs pruned {p:.1%}, "
          f"gap {gap*100:+.1f}pp -> {'HELD' if gap >= 0.15 else 'FALSIFIED'}")
else:
    print(f"  P-RAG4  NOT SCORED — gate P-RAG6 failed (base near chance; the design has no signal)")
pos_p = abs(rate[("pruned","C3a")] - rate[("pruned","C3b")])
print(f"\n  position bias: base {pos_b*100:.1f}pp, pruned {pos_p*100:.1f}pp")
print(f"  (a large bias means order, not content, decides -- read the orders separately)")
