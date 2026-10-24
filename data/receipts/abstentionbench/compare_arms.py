#!/usr/bin/env python3
"""PREREG_ABSTENTIONBENCH Addendum 2: paired comparison of two subject arms under one judge variant.
Only items with a non-error response AND a non-None verdict in BOTH arms count (completed pairs). Abstention is the
positive class. Reports pooled precision / recall / F1 and mean F1 over datasets for each arm, the B - A differences with
paired bootstrap 95 % intervals (10,000 resamples of items within each dataset), per-dataset F1, forced reasoning cuts,
and median reasoning tokens by label.
Usage: compare_arms.py --checkout DIR --a Q27OFF --b Q27ON --judge norefs|exact [--out FILE]"""
import argparse, json, random, statistics as st
from pathlib import Path
HERE = Path(__file__).resolve().parent; RAW = HERE / "raw"
ap = argparse.ArgumentParser(); ap.add_argument("--checkout", required=True); ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
ap.add_argument("--judge", required=True); ap.add_argument("--out"); ap.add_argument("--resamples", type=int, default=10000); ap.add_argument("--seed", type=int, default=20261024)
a = ap.parse_args()
load = lambda p: {(r["dataset"], r["index"]): r for r in map(json.loads, open(p)) if "error" not in r}
R = {x: load(RAW / f"{x}.jsonl") for x in (a.a, a.b)}; J = {x: load(RAW / f"{x}.judge_{a.judge}.jsonl") for x in (a.a, a.b)}
keys = sorted(k for k in R[a.a] if k in R[a.b] and k in J[a.a] and k in J[a.b] and J[a.a][k]["verdict"] is not None and J[a.b][k]["verdict"] is not None)
lab = {k: bool(J[a.a][k]["should_abstain"]) for k in keys}
def prf(ks, arm):
    tp = sum(1 for k in ks if lab[k] and J[arm][k]["verdict"]); fp = sum(1 for k in ks if not lab[k] and J[arm][k]["verdict"])
    fn = sum(1 for k in ks if lab[k] and not J[arm][k]["verdict"])
    P = tp / (tp + fp) if tp + fp else 0.0; Rc = tp / (tp + fn) if tp + fn else 0.0
    return P, Rc, (2 * P * Rc / (P + Rc) if P + Rc else 0.0)
by = {}
for k in keys: by.setdefault(k[0], []).append(k)
def stats(sample_by):
    allk = [k for v in sample_by.values() for k in v]; out = {}
    for arm in (a.a, a.b):
        P, Rc, F = prf(allk, arm); out[arm] = {"precision": P, "recall": Rc, "f1": F, "mean_f1": st.mean(prf(v, arm)[2] for v in sample_by.values())}
    return out
point = stats(by); rng = random.Random(a.seed); boots = []
for _ in range(a.resamples):
    s = stats({d: [rng.choice(v) for _ in v] for d, v in by.items()})
    boots.append({m: s[a.b][m] - s[a.a][m] for m in ("precision", "recall", "f1", "mean_f1")})
ci = lambda m: [round(sorted(b[m] for b in boots)[int(q * a.resamples)], 3) for q in (0.025, 0.975)]
tok = lambda r: (r.get("usage1") or r.get("usage") or {}).get("completion_tokens", 0) if r.get("reasoning") else 0
out = {"judge": a.judge, "arms": [a.a, a.b], "pairs": len(keys), "should_abstain": sum(lab.values()), "datasets": len(by),
       "arm_stats": {arm: {m: round(v, 3) for m, v in point[arm].items()} for arm in (a.a, a.b)},
       "diff_b_minus_a": {m: {"point": round(point[a.b][m] - point[a.a][m], 3), "ci95": ci(m)} for m in ("precision", "recall", "f1", "mean_f1")},
       "per_dataset_f1": {d: {a.a: round(prf(v, a.a)[2], 3), a.b: round(prf(v, a.b)[2], 3), "n": len(v)} for d, v in sorted(by.items())},
       "forced_cuts": {arm: {"should_abstain": sum(1 for k in keys if lab[k] and R[arm][k].get("forced")), "should_answer": sum(1 for k in keys if not lab[k] and R[arm][k].get("forced"))} for arm in (a.a, a.b)},
       "rows_with_reasoning": {arm: sum(1 for k in keys if R[arm][k].get("reasoning")) for arm in (a.a, a.b)},
       "median_reasoning_tokens": {arm: {"should_abstain": st.median([tok(R[arm][k]) for k in keys if lab[k]] or [0]),
                                         "should_answer": st.median([tok(R[arm][k]) for k in keys if not lab[k]] or [0])} for arm in (a.a, a.b)}}
json.dump(out, open(a.out or HERE / f"RESULT_{a.a}_vs_{a.b}_{a.judge}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "per_dataset_f1"}, indent=1))
