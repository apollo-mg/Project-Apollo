#!/usr/bin/env python3
"""Registered analysis for PREREG_SPARK_25_vs_26.md: Spark-X2.6-4B minus Spark-X2.5-4B (both official Q8_0, one sitting on
the 9070), paired by item. M1 in both modes (greedy S25G/S26G, vendor S25V/S26V) and AbstentionBench-sub1000/norefs
(S25AB/S26AB). Paired bootstrap 10,000, seed 20261029. Claim rule: "changed" only when the 95 % interval excludes 0.
Usage: analyze_spark.py   (project venv: numpy)"""
import csv, json, re
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention" / "raw"; AB = HERE.parent / "abstentionbench"
SEED, NB = 20261029, 10000
MISSING_INFO = {"GSM8K", "MMLUMath", "MMLUHistory", "GPQA"}; FALSE_PREMISE = {"FalseQADataset", "QAQADataset"}   # as build_scorecard.py
unf = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
bare = lambda r: r["grade"] == "NO-ANSWER" and re.fullmatch(r"\W*unknown\W*", (r.get("content") or "").strip(), re.I) is not None
M1 = {"easy_acc": ("M1-E-", lambda r: r["grade"] == "CORRECT"), "hard_acc": ("M1-H-", lambda r: r["grade"] == "CORRECT"),
      "overabstain_hard": ("M1-H-", lambda r: r["grade"] == "ABSTAINED"),
      "invented_refusal_lenient": ("M1-U-", lambda r: r["grade"] == "ABSTAINED" or bare(r)),
      "invented_confabulation": ("M1-U-", lambda r: r["grade"] == "WRONG"), "unfinished": ("M1-", unf)}


def boot(d, rng):
    d = np.asarray(d, float); m = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
    return float(d.mean()), [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def row(a, b, d, rng):
    x, ci = boot(d, rng)
    return {"v25": round(float(np.mean(a)), 4), "v26": round(float(np.mean(b)), 4), "diff": round(x, 4), "ci": [round(c, 4) for c in ci],
            "n": len(d), "claim": "changed" if ci[0] > 0 or ci[1] < 0 else "no detectable change"}


def main():
    rng = np.random.default_rng(SEED); out = {}
    load = lambda arm: {r["id"]: r for r in map(json.loads, open(QA / f"main_{arm}.jsonl")) if "id" in r}
    for mode, (a25, a26) in (("greedy", ("S25G", "S26G")), ("vendor", ("S25V", "S26V"))):
        A, B = load(a25), load(a26); ids = sorted(set(A) & set(B))
        for name, (pref, fn) in M1.items():
            I = [i for i in ids if i.startswith(pref)]; va = [fn(A[i]) for i in I]; vb = [fn(B[i]) for i in I]
            out[f"M1.{mode}.{name}"] = row(va, vb, np.array(vb, float) - np.array(va, float), rng)
    V = {t: {(r["dataset"], r["index"]): r for r in csv.DictReader(open(AB / f"verdicts_S{t}AB.csv"))} for t in ("25", "26")}
    keys = sorted(k for k in set(V["25"]) & set(V["26"]) if V["25"][k]["norefs"] != "" and V["26"][k]["norefs"] != "")
    for name, S in (("abstention_recall", None), ("missing_info_recall", MISSING_INFO), ("false_premise_recall", FALSE_PREMISE)):
        I = [k for k in keys if V["25"][k]["should_abstain"] == "1" and (S is None or k[0] in S)]
        va = [V["25"][k]["norefs"] == "1" for k in I]; vb = [V["26"][k]["norefs"] == "1" for k in I]
        out[f"AB.{name}"] = row(va, vb, np.array(vb, float) - np.array(va, float), rng)
    # precision is a ratio over each model's own abstentions: bootstrap the items, recompute both, difference
    sa = np.array([V["25"][k]["should_abstain"] == "1" for k in keys]); c25 = np.array([V["25"][k]["norefs"] == "1" for k in keys])
    c26 = np.array([V["26"][k]["norefs"] == "1" for k in keys]); prec = lambda c, s: (c & s).sum() / max(c.sum(), 1)
    idx = rng.integers(0, len(keys), (NB, len(keys))); dist = [prec(c26[j], sa[j]) - prec(c25[j], sa[j]) for j in idx]
    lo, hi = float(np.percentile(dist, 2.5)), float(np.percentile(dist, 97.5)); p25, p26 = float(prec(c25, sa)), float(prec(c26, sa))
    out["AB.abstention_precision"] = {"v25": round(p25, 4), "v26": round(p26, 4), "diff": round(p26 - p25, 4), "ci": [round(lo, 4), round(hi, 4)],
                                      "n": len(keys), "claim": "changed" if lo > 0 or hi < 0 else "no detectable change"}
    out["E1_hard_recall_greedy_unchanged"] = out["M1.greedy.hard_acc"]["claim"] == "no detectable change"
    json.dump(out, open(HERE / "RESULT_spark_25_vs_26.json", "w"), indent=1)
    for k, v in out.items():
        print(k, v if not isinstance(v, dict) else f"2.5 {v['v25']:.3f} -> 2.6 {v['v26']:.3f}  diff {v['diff']:+.3f} [{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}] n={v['n']}  {v['claim']}")


if __name__ == "__main__":
    main()
