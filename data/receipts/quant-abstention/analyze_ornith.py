#!/usr/bin/env python3
"""Registered analysis for PREREG_ORNITH.md: ORN (Ornith-1.5-122B UD-Q3_K_XL, thinking off) vs stored BEAM, SVNV, FNQ2,
BOLT, FLNT and the 27B Q8_0 (C.A), paired by item. Paired bootstrap 10,000, seed 20261022. Usage: analyze_ornith.py"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261022, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="RESULT_ornith.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    R = {k: load(arm) for k, arm in (("orn", "ORN"), ("beam", "BEAM"), ("sv", "SVNV"), ("fn", "FNQ2"),
                                     ("bolt", "BOLT"), ("flnt", "FLNT"), ("ref", "C.A"))}
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()])); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"
    unfinished = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
    v = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda k1, k2, g, fn: boot(v(k1, g, fn) - v(k2, g, fn), rng)
    rates = {k: {"E_acc": v(k, "E", C).mean(), "H_acc": v(k, "H", C).mean(), "H_timid": v(k, "H", A).mean(),
                 "U_refuse": v(k, "U", A).mean(), "unfinished": float(np.mean([unfinished(R[k][i]) for i in ids]))} for k in R}
    P = {}
    x, ci = d("orn", "ref", "H", C); P["P1"] = {"H_acc_orn_minus_27b": [x, ci], "holds": x >= 0.10 and ci[0] > 0}
    x, ci = d("orn", "ref", "U", A); P["P2"] = {"U_refuse_orn_minus_27b": [x, ci], "holds": x >= 0 and ci[0] > -0.07}
    x, ci = d("orn", "flnt", "U", A); P["P3"] = {"U_refuse_orn_minus_flnt": [x, ci], "holds": x >= 0.15 and ci[0] > 0}
    u = rates["orn"]["unfinished"]; P["P4"] = {"unfinished_share": u, "holds": u <= 0.02}
    rep = {f"{m}_orn_minus_{k}": list(d("orn", k, g, fn)) for k in ("beam", "sv", "fn", "bolt", "flnt", "ref")
           for m, g, fn in (("H_acc", "H", C), ("U_refuse", "U", A), ("E_acc", "E", C))}
    rep["orn_reasoning_nonempty"] = sum(1 for i in ids if (R["orn"][i].get("reasoning") or ""))
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(y, 3) for m, y in r.items()} for k, r in rates.items()}))
    for k, y in P.items(): print(k, "HOLDS" if y["holds"] else "does not hold", {m: y[m] for m in y if m != "holds"})
    for k, y in rep.items(): print("reported", k, y)


if __name__ == "__main__":
    main()
