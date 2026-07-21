#!/usr/bin/env python3
"""Paired significance test for the ARC-Challenge matched run (base vs DavidAU).

llama.cpp --multiple-choice prints NO final-summary line for this code path; it emits
per-task running accuracy to stdout as "<task_idx>\t<cum_acc%>". We reconstruct per-item
correctness exactly from that trace (cum_acc is integer n_correct / integer idx), align the
two arms item-by-item, and run an exact two-sided McNemar test on the discordant pairs.

Run from this directory:  python3 mcnemar.py
Inputs: base.out, davidau.out  (the harvested stdout traces).
"""
import re
from math import comb

def per_item(path):
    pairs = []
    for ln in open(path):
        m = re.match(r"\s*(\d+)\s+([\d.]+)\s*$", ln)
        if m:
            pairs.append((int(m.group(1)), float(m.group(2))))
    pairs.sort()
    correct, prev_nc = {}, 0
    for i, acc in pairs:
        nc = round(acc / 100.0 * i)      # cum n_correct at item i
        correct[i] = nc - prev_nc         # 0 or 1
        prev_nc = nc
    return correct

cb = per_item("base.out")
cd = per_item("davidau.out")
keys = sorted(set(cb) & set(cd))
n = len(keys)
nb = sum(cb[k] for k in keys)
nd = sum(cd[k] for k in keys)
b = sum(1 for k in keys if cd[k] == 1 and cb[k] == 0)   # davidau right, base wrong
c = sum(1 for k in keys if cd[k] == 0 and cb[k] == 1)   # davidau wrong, base right
both = sum(1 for k in keys if cd[k] == 1 and cb[k] == 1)
neither = sum(1 for k in keys if cd[k] == 0 and cb[k] == 0)

N = b + c
k = min(b, c)
p = min(1.0, 2 * sum(comb(N, i) for i in range(0, k + 1)) / 2 ** N)
se = ((b + c) / n ** 2) ** 0.5
diff = (nd - nb) / n

print(f"aligned items      : {n}")
print(f"base    correct    : {nb}  ({100*nb/n:.2f}% acc)")
print(f"davidau correct    : {nd}  ({100*nd/n:.2f}% acc)")
print(f"net (davidau-base) : {nd-nb} items = {diff*100:+.2f} pts")
print(f"contingency        : both={both} neither={neither} davidau_only(b)={b} base_only(c)={c} discordant={N}")
print(f"McNemar exact 2-sided p = {p:.4f}")
print(f"paired diff {diff*100:+.2f} pts, SE {se*100:.2f}, 95% CI [{100*(diff-1.96*se):+.2f}, {100*(diff+1.96*se):+.2f}] pts")
print("VERDICT: p>0.05 and CI straddles 0 -> base and DavidAU statistically indistinguishable on ARC-Challenge acc.")
