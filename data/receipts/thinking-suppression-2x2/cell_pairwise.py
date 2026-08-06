#!/usr/bin/env python3
"""Paired per-problem comparison of reasoning length between 2x2 cells.

A ratio of means over 15 problems is exactly the statistic that one long trace can
drive. This does the paired version: same problem, both cells, sign test + median
ratio, so an outlier can move the mean but not the sign count.
"""
import json, sys, glob, os

OUT = "/home/mark/hep/out"

def load(tag):
    p = f"/home/mark/hep/sup_results_{tag}.json"
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    return {r["task_id"]: r for r in d["results"]}, d

def cmp_cells(a_tag, b_tag):
    A = load(a_tag); B = load(b_tag)
    if not A or not B:
        print(f"  (missing results for {a_tag} or {b_tag})"); return
    Am, Ad = A; Bm, Bd = B
    ids = sorted(set(Am) & set(Bm), key=lambda t: int(t.split("/")[1]))
    print(f"\n=== {a_tag}  vs  {b_tag}   ({len(ids)} paired problems) ===")
    ra = [Am[i]["rc_chars"][0] for i in ids]
    rb = [Bm[i]["rc_chars"][0] for i in ids]
    mean_a, mean_b = sum(ra)/len(ra), sum(rb)/len(rb)
    print(f"  mean  {a_tag}={mean_a:8.0f}   {b_tag}={mean_b:8.0f}   ratio={mean_b/mean_a:.2f}x")
    sa, sb = sorted(ra), sorted(rb)
    print(f"  median{a_tag}={sa[len(sa)//2]:8.0f}   {b_tag}={sb[len(sb)//2]:8.0f}   "
          f"ratio={sb[len(sb)//2]/sa[len(sa)//2]:.2f}x")
    ratios = sorted(y/x for x, y in zip(ra, rb) if x > 0)
    print(f"  median per-problem ratio = {ratios[len(ratios)//2]:.2f}x   "
          f"(min {ratios[0]:.2f}x, max {ratios[-1]:.2f}x)")
    up = sum(1 for x, y in zip(ra, rb) if y > x)
    print(f"  SIGN TEST: {b_tag} longer on {up}/{len(ids)} problems")
    # what happens if we drop the single biggest contributor to the gap
    diffs = sorted(range(len(ids)), key=lambda k: rb[k]-ra[k], reverse=True)
    k = diffs[0]
    ra2 = [v for j, v in enumerate(ra) if j != k]
    rb2 = [v for j, v in enumerate(rb) if j != k]
    print(f"  drop largest single gap ({ids[k]}: {ra[k]} -> {rb[k]}): "
          f"ratio becomes {(sum(rb2)/len(rb2))/(sum(ra2)/len(ra2)):.2f}x")
    print(f"  per-problem: " + " ".join(f"{x}->{y}" for x, y in zip(ra, rb)))

have = sorted(os.path.basename(p).replace("sup_results_", "").replace(".json", "")
              for p in glob.glob("/home/mark/hep/sup_results_*.json"))
print("cells with results:", have)
if "base" in have and "persona" in have:
    cmp_cells("base", "persona")
if "base" in have and "tools" in have:
    cmp_cells("base", "tools")
if "base" in have and "both" in have:
    cmp_cells("base", "both")
