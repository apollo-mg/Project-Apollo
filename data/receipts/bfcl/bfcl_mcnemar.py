#!/usr/bin/env python3
"""
Paired matched-item analysis: Puzzle-75B-A9B (UDIQ4XL) vs Qwen3.6-27B (Q8) on the
identical 201-item BFCL v4 AST subset. Reconstructs per-item pass/fail from BFCL score
files (summary line + failure lines only), cross-checks each category's accuracy against
BFCL's own summary, and runs an exact two-sided McNemar test on the discordant pairs.
"""
import json, os, sys, math
from math import comb

SP = os.path.expanduser("~/bfcl_venv/lib/python3.11/site-packages")
MODELS = {
    "puzzle": "apollo_puzzle-75b-a9b-udiq4xl",
    "qwen":   "apollo_qwen3.6-27b-q8",
}
CATS = ["simple_python","simple_java","simple_javascript","multiple","parallel","parallel_multiple"]

def load_model(tag, mdir):
    """Return {id: (category, correct_bool)} and per-cat (correct,total) from summary."""
    per_item = {}
    per_cat_summary = {}
    for cat in CATS:
        rf = f"{SP}/result/{mdir}/non_live/BFCL_v4_{cat}_result.json"
        sf = f"{SP}/score/{mdir}/non_live/BFCL_v4_{cat}_score.json"
        ids = []
        with open(rf) as f:
            for line in f:
                line=line.strip()
                if line: ids.append(json.loads(line)["id"])
        failed=set(); summ=None
        with open(sf) as f:
            for i,line in enumerate(f):
                line=line.strip()
                if not line: continue
                d=json.loads(line)
                if i==0: summ=d
                else: failed.add(d["id"])
        per_cat_summary[cat]=(summ["correct_count"], summ["total_count"])
        # cross-check: reconstructed correct == summary correct
        recon_correct = sum(1 for _id in ids if _id not in failed)
        assert recon_correct == summ["correct_count"], \
            f"{tag}/{cat}: reconstructed {recon_correct} != summary {summ['correct_count']}"
        assert len(ids) == summ["total_count"], \
            f"{tag}/{cat}: {len(ids)} ids != summary total {summ['total_count']}"
        for _id in ids:
            per_item[_id] = (cat, _id not in failed)
    return per_item, per_cat_summary

P, Psum = load_model("puzzle", MODELS["puzzle"])
Q, Qsum = load_model("qwen",   MODELS["qwen"])

# IDs must match exactly (same subset)
assert set(P)==set(Q), f"ID mismatch: only-puzzle={set(P)-set(Q)}, only-qwen={set(Q)-set(P)}"
ids = sorted(P, key=lambda x:(P[x][0], x))
N=len(ids)

# per-category table
print(f"{'category':20s} {'n':>3} {'Puzzle':>10} {'Qwen':>10}")
tot_p=tot_q=0
for cat in CATS:
    pc,pt = Psum[cat]; qc,qt = Qsum[cat]
    tot_p+=pc; tot_q+=qc
    print(f"{cat:20s} {pt:>3} {pc:>3}/{pt:<3}={pc/pt*100:5.1f}% {qc:>3}/{qt:<3}={qc/qt*100:5.1f}%")
print(f"{'OVERALL':20s} {N:>3} {tot_p:>3}/{N:<3}={tot_p/N*100:5.1f}% {tot_q:>3}/{N:<3}={tot_q/N*100:5.1f}%")

# 2x2 discordance
a=b=c=d=0
for _id in ids:
    pcorr=P[_id][1]; qcorr=Q[_id][1]
    if pcorr and qcorr: a+=1
    elif pcorr and not qcorr: b+=1
    elif not pcorr and qcorr: c+=1
    else: d+=1
print(f"\n2x2 (rows=Puzzle, cols=Qwen):")
print(f"                Qwen✓   Qwen✗")
print(f"  Puzzle✓   a={a:4d}  b={b:4d}")
print(f"  Puzzle✗   c={c:4d}  d={d:4d}")
print(f"  discordant: b(Puzzle-only)={b}, c(Qwen-only)={c}")

# exact two-sided McNemar on discordant pairs
n=b+c; k=min(b,c)
if n==0:
    p_exact=1.0
else:
    tail=sum(comb(n,i) for i in range(0,k+1))*(0.5**n)
    p_exact=min(1.0, 2*tail)
print(f"\nExact McNemar (two-sided binomial on n={n} discordant, k=min={k}): p = {p_exact:.4g}")
print(f"Net paired delta (Qwen - Puzzle) = {c-b:+d} items = {(c-b)/N*100:+.1f} pp")

# parallel-specific headline
print("\n--- parallel-family breakdown (the headline differential) ---")
for cat in ("parallel","parallel_multiple"):
    pc,pt=Psum[cat]; qc,qt=Qsum[cat]
    print(f"  {cat:18s} Puzzle {pc}/{pt}={pc/pt*100:.1f}%  vs  Qwen {qc}/{qt}={qc/qt*100:.1f}%")

# write per-item CSV for the receipts
out=os.path.join(os.path.dirname(os.path.abspath(__file__)),"bfcl_per_item.csv")
with open(out,"w") as f:
    f.write("id,category,puzzle_correct,qwen_correct\n")
    for _id in ids:
        f.write(f"{_id},{P[_id][0]},{int(P[_id][1])},{int(Q[_id][1])}\n")
print(f"\nper-item vectors -> {out} ({N} rows)")
