#!/usr/bin/env python3
"""Registered analysis for PREREG_BOLT_SPLIT.md (compression vs 2-bit step in Bolt). Committed before any new row.

Same readouts as analyze_bolt.py. Paired differences by item, 95 % percentile bootstrap (10,000, seed 20261017).
Usage: analyze_bolt_split.py [--q8 BOLTQ8] [--pq2 BOLTPQ2] [--bolt BOLT] [--sv SVNV] [--ref C.A] [--out RESULT_bolt_split.json]
Missing arms are skipped (the two new arms run on different hosts and may finish apart).
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261017, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    for k, v in (("q8", "BOLTQ8"), ("pq2", "BOLTPQ2"), ("bolt", "BOLT"), ("sv", "SVNV"), ("ref", "C.A")):
        ap.add_argument(f"--{k}", default=v)
    ap.add_argument("--out", default="RESULT_bolt_split.json")
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    arms = {"q8": a.q8, "pq2": a.pq2, "bolt": a.bolt, "sv": a.sv, "ref": a.ref}
    R = {}
    for k, arm in arms.items():
        try: R[k] = load(arm)
        except FileNotFoundError: print(f"missing arm {arm} ({k})", file=sys.stderr)
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()]))
    grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"; T = lambda r: r["grade"] == "TRUNCATED"
    vec = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED)
    diff = lambda k1, k2, g, fn: boot(vec(k1, g, fn) - vec(k2, g, fn), rng)
    out = {"arms": arms, "n": {g: len(v) for g, v in grp.items()}, "rates": {}, "slot_U": {}, "predictions": {}, "reported": {}}
    for k in R:
        out["rates"][k] = {"E_acc": vec(k, "E", C).mean(), "H_acc": vec(k, "H", C).mean(), "H_timid": vec(k, "H", A).mean(),
                           "U_refuse": vec(k, "U", A).mean(), "truncated": float(np.mean([T(R[k][i]) for i in ids]))}
        out["slot_U"][k] = float(np.mean([R[k][i]["P_abs"] for i in grp["U"]]))
    P = out["predictions"]
    if {"q8", "sv"} <= R.keys():
        d, ci = diff("q8", "sv", "U", A); P["P1"] = {"U_refuse_q8_minus_sv": [d, ci], "holds": d <= -0.20 and ci[1] < 0}
        d, ci = diff("q8", "sv", "H", C); P["P3"] = {"H_acc_q8_minus_sv": [d, ci], "holds": d <= -0.15 and ci[1] < 0}
    if {"q8", "sv", "bolt"} <= R.keys():
        comp = out["rates"]["sv"]["U_refuse"] - out["rates"]["q8"]["U_refuse"]
        quant = out["rates"]["q8"]["U_refuse"] - out["rates"]["bolt"]["U_refuse"]
        P["P2"] = {"compression_gap": comp, "twobit_gap": quant, "holds": comp > quant}
        out["reported"]["H_acc_q8_minus_bolt"] = list(diff("q8", "bolt", "H", C))
        out["reported"]["U_refuse_q8_minus_bolt"] = list(diff("q8", "bolt", "U", A))
    if {"pq2", "bolt"} <= R.keys():
        d, ci = diff("pq2", "bolt", "U", A); P["P4"] = {"U_refuse_pq2_minus_bolt": [d, ci], "holds": d >= 0 and ci[0] > -0.07}
        out["reported"]["H_acc_pq2_minus_bolt"] = list(diff("pq2", "bolt", "H", C))
    for k in ("q8", "pq2"):
        if k in R:
            P[f"P5_{k}"] = {"truncated_share": out["rates"][k]["truncated"], "holds": out["rates"][k]["truncated"] <= 0.02}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(v, 3) for m, v in r.items()} for k, r in out["rates"].items()}))
    print("slot_U", {k: round(v, 3) for k, v in out["slot_U"].items()})
    for k, v in P.items(): print(k, "HOLDS" if v["holds"] else "does not hold", {m: v[m] for m in v if m != "holds"})
    for k, v in out["reported"].items(): print("reported", k, v)


if __name__ == "__main__":
    main()
