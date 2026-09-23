#!/usr/bin/env python3
"""Analysis fixed in data/receipts/argus-v2/PREREG_HEMMINGWAY_BREVITY.md.
Per item: geometric mean over reps; log ratio H/S within each prompt condition.
R+ = brevity SOUL, R- = no SOUL, interaction = R- minus R+ (paired by item).
All 40 items (verbosity is not a pass/fail property). Wall time deliberately NOT analysed.
usage: argus_brevity_2x2.py [runs/brev dir]"""
import json, math, statistics as st, sys, collections
from scipy.stats import ttest_1samp, wilcoxon
D = sys.argv[1] if len(sys.argv) > 1 else "argus/runs/brev"
fam = json.load(open("argus/families_v4.json")); items = fam if isinstance(fam, list) else fam.get("items", fam.get("scenarios", []))
FAMILY = {i["id"]: i["id"].split("-")[0] for i in items}
def geo(cell, metric):
    d = collections.defaultdict(list)
    for l in open(f"{D}/{cell}.jsonl"):
        r = json.loads(l)
        if r["verdict"] in ("INFRA", "TOOL-FAIL"): continue
        v = {"reply": r["consumption"]["reply_chars"], "think": r["consumption"]["think_chars"],
             "tools": len(r["tool_calls"])}[metric]
        d[r["id"]].append(max(v, 1))
    return {i: math.exp(st.mean(map(math.log, v))) for i, v in d.items()}
def summ(lr, label):
    n = len(lr); m = st.mean(lr); se = st.stdev(lr) / math.sqrt(n)
    tp = ttest_1samp(lr, 0).pvalue; nz = [x for x in lr if x != 0]
    wp = wilcoxon(nz).pvalue if len(nz) > 5 else float("nan")
    print(f"  {label:34s} {math.exp(m):5.2f}x  CI [{math.exp(m-2.02*se):.2f}x, {math.exp(m+2.02*se):.2f}x]"
          f"  t p={tp:.4f}  Wilcoxon p={wp:.4f}  n={n}  (>1 on {sum(x>0 for x in lr)})")
    return m, se
for metric in ("reply", "think", "tools"):
    S1, H1, S0, H0 = (geo(c, metric) for c in ("stock_soul", "hemm_soul", "stock_none", "hemm_none"))
    ids = sorted(set(S1) & set(H1) & set(S0) & set(H0))
    print(f"=== {metric}_chars ===" if metric != "tools" else "=== tool calls ===")
    print(f"  medians: S+ {st.median(S1[i] for i in ids):.0f}  H+ {st.median(H1[i] for i in ids):.0f}"
          f"  S- {st.median(S0[i] for i in ids):.0f}  H- {st.median(H0[i] for i in ids):.0f}")
    rp = [math.log(H1[i] / S1[i]) for i in ids]; rm = [math.log(H0[i] / S0[i]) for i in ids]
    summ(rp, "R+  H/S WITH brevity prompt")
    summ(rm, "R-  H/S WITHOUT prompt")
    summ([b - a for a, b in zip(rp, rm)], "interaction  R- / R+")
    summ([math.log(S0[i] / S1[i]) for i in ids], "B2  stock: no-prompt / prompt")
    summ([math.log(H0[i] / H1[i]) for i in ids], "    hemm:  no-prompt / prompt")
    if metric == "think":
        print("  exploratory (Swift pattern): H/S reasoning ratio by family, pooled over both prompts")
        for f in sorted(set(FAMILY[i] for i in ids)):
            fi = [i for i in ids if FAMILY[i] == f]
            lr = [math.log(H1[i] / S1[i]) for i in fi] + [math.log(H0[i] / S0[i]) for i in fi]
            print(f"     {f:4s} {math.exp(st.mean(lr)):.2f}x  (n={len(lr)})")
    print()
