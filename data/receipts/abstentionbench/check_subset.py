#!/usr/bin/env python3
"""Registered check for PREREG_ABENCH_SUBSET.md: the four card metrics on the full fast subset vs subset_<N>, for the
stored anchors (LLAMA8 norefs, Q27OFF off_norefs, Q27ON on_norefs). PASS: every full-set value lies inside the subset's
95 % Wilson interval (12 checks). Reported, not judged: the Q27ON - Q27OFF paired recall difference on the subset
(bootstrap 10,000, seed 20261028) next to the full set's. This measures item-sampling error on the same verdicts: a
sanity check, not a validation of the subset. Usage: check_subset.py [--n 500]   (project venv: numpy)"""
import argparse, csv, json, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
MISSING_INFO = {"GSM8K", "MMLUMath", "MMLUHistory", "GPQA"}; FALSE_PREMISE = {"FalseQADataset", "QAQADataset"}   # as build_scorecard.py
ARMS = (("LLAMA8", "verdicts_LLAMA8.csv", "norefs"), ("Q27OFF", "verdicts_Q27.csv", "off_norefs"), ("Q27ON", "verdicts_Q27.csv", "on_norefs"))


def wilson(k, n, z=1.96):   # as build_scorecard.py
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


def metrics(rows, col):
    sa = [r for r in rows if r["should_abstain"] == "1"]; called = [r for r in rows if r[col] == "1"]
    out = {"abstention_recall": (sum(r[col] == "1" for r in sa), len(sa)),
           "abstention_precision": (sum(r["should_abstain"] == "1" for r in called), len(called))}
    for name, S in (("missing_info_recall", MISSING_INFO), ("false_premise_recall", FALSE_PREMISE)):
        sub = [r for r in sa if r["dataset"] in S]; out[name] = (sum(r[col] == "1" for r in sub), len(sub))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=500); a = ap.parse_args()
    S = {(r["dataset"], r["index"]): r for r in csv.DictReader(open(HERE / f"subset_{a.n}.csv"))}
    res, ok, V = {}, True, {}
    for arm, f, col in ARMS:
        rows = [r for r in csv.DictReader(open(HERE / f)) if r[col] != ""]   # missing verdicts excluded the same way on both
        Vk = {(r["dataset"], r["index"]): r for r in rows}; V[arm] = (Vk, col)
        miss = set(S) - set(Vk); assert not miss, f"{arm}: {len(miss)} subset items have no verdict"
        assert all(Vk[k]["should_abstain"] == S[k]["should_abstain"] for k in S), f"{arm}: should_abstain disagrees"
        full, sub = metrics(rows, col), metrics([Vk[k] for k in S], col); res[arm] = {}
        for m in full:
            fv = full[m][0] / full[m][1]; sv, lo, hi = wilson(*sub[m]); inside = lo <= fv <= hi; ok &= inside
            res[arm][m] = {"full": round(fv, 4), "full_n": full[m][1], "subset": round(sv, 4), "ci": [round(lo, 4), round(hi, 4)], "n": sub[m][1], "inside": inside}
            print(f"{arm:7s} {m:22s} full {fv:.3f} (n={full[m][1]:4d})  subset {sv:.3f} [{lo:.3f}, {hi:.3f}] (n={sub[m][1]:3d})  {'inside' if inside else 'OUTSIDE'}")
    (on, c1), (off, c0) = V["Q27ON"], V["Q27OFF"]
    def diff(keys):
        return np.array([int(on[k][c1] == "1") - int(off[k][c0] == "1") for k in keys if on[k]["should_abstain"] == "1"], float)
    ds, df = diff(S), diff(set(on) & set(off)); rng = np.random.default_rng(20261028)
    m = ds[rng.integers(0, len(ds), (10000, len(ds)))].mean(1)
    paired = {"subset": [float(ds.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)), len(ds)], "full": [float(df.mean()), len(df)]}
    print(f"Q27ON - Q27OFF recall: subset {ds.mean():+.3f} [{paired['subset'][1]:+.3f}, {paired['subset'][2]:+.3f}] (n={len(ds)}), full {df.mean():+.3f} (n={len(df)})")
    print("PASS: all full-set values inside the subset intervals" if ok else "FAIL: at least one full-set value outside its subset interval")
    json.dump({"n": a.n, "pass": ok, "metrics": res, "paired_recall_Q27ON_minus_Q27OFF": paired}, open(HERE / f"RESULT_abench_subset_{a.n}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
