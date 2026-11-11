#!/usr/bin/env python3
"""PREREG_SAGE_SAMPLED.md analysis: two models each run K times on M1 with different seeds (the same seeds for both).
Per item, each metric is the mean of its 0/1 indicator over the K replicates; a rate is the mean over items. Paired by
item: B - A, 95 % percentile bootstrap over items (10,000 resamples, seed 20261111). Metric definitions are imported
from ds41-h2h/analyze_ds41.py (METRICS: E/H accuracy, H abstained, U refused strict and lenient, U confabulated,
unfinished). Optional: each model's sampled mean against its own greedy arm, paired the same way.
Usage: analyze_k.py --a A1,A2,A3 --b B1,B2,B3 [--a-greedy ARM] [--b-greedy ARM] [--json OUT]   (arm names under raw/)"""
import argparse, importlib.util, json, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("analyze_ds41", HERE.parent / "ds41-h2h" / "analyze_ds41.py")
ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)


def rows(arm):
    return ad.load(HERE / "raw" / f"main_{arm}.jsonl")[1]


def per_item(arms, metric):
    """{id: mean over the arms (replicates) of the metric's indicator}, items of the metric's group only."""
    g, pred = ad.METRICS[metric]
    R = [rows(a) for a in arms]
    ids = sorted(set.intersection(*(set(r) for r in R)))
    return {i: sum(int(pred(r[i])) for r in R) / len(R) for i in ids if g is None or ad.group(i) == g}


def compare(A, B, seed=20261111, n_boot=10000):
    ids = sorted(set(A) & set(B)); d = [B[i] - A[i] for i in ids]; n = len(d); rng = random.Random(seed)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return {"n": n, "A": round(sum(A[i] for i in ids) / n, 4), "B": round(sum(B[i] for i in ids) / n, 4),
            "diff": round(sum(d) / n, 4), "ci95": [round(boots[int(0.025 * n_boot)], 4), round(boots[int(0.975 * n_boot) - 1], 4)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--a-greedy"); ap.add_argument("--b-greedy"); ap.add_argument("--json")
    a = ap.parse_args()
    A, B = a.a.split(","), a.b.split(",")
    out = {"A": A, "B": B, "primary_B_minus_A": {}, "A_sampled_minus_greedy": {}, "B_sampled_minus_greedy": {}}
    for m in ad.METRICS:
        pa, pb = per_item(A, m), per_item(B, m)
        out["primary_B_minus_A"][m] = compare(pa, pb)
        for key, arms, greedy in (("A_sampled_minus_greedy", A, a.a_greedy), ("B_sampled_minus_greedy", B, a.b_greedy)):
            if greedy:
                out[key][m] = compare(per_item([greedy], m), per_item(arms, m))
    for key in ("primary_B_minus_A", "A_sampled_minus_greedy", "B_sampled_minus_greedy"):
        if out[key]:
            print(f"== {key}")
            for m, r in out[key].items():
                print(f"{m:18s} n={r['n']:3d}  A {r['A']:.3f}  B {r['B']:.3f}  diff {r['diff']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
