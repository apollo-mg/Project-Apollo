#!/usr/bin/env python3
"""Registered analysis for PREREG_SAGE.md Addendum 1: SGTHK1 / SGVER1 (Sage-A1.5 Q8_0, thinking on, Sage's recommended
sampling, verification off / on) vs each other and the stored SGTHK, SGVER, SGOFF, paired by item. Paired bootstrap
10,000, seed 20261025. Usage: analyze_sage_t1.py"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261025, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="RESULT_sage_t1.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    R = {k: load(arm) for k, arm in (("t1thk", "SGTHK1"), ("t1ver", "SGVER1"), ("sgthk", "SGTHK"), ("sgver", "SGVER"), ("sgoff", "SGOFF"))}
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()])); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"
    unfinished = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
    v = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda k1, k2, g, fn: boot(v(k1, g, fn) - v(k2, g, fn), rng)
    rates = {k: {"E_acc": v(k, "E", C).mean(), "H_acc": v(k, "H", C).mean(), "H_timid": v(k, "H", A).mean(),
                 "U_refuse": v(k, "U", A).mean(), "unfinished": float(np.mean([unfinished(R[k][i]) for i in ids]))} for k in R}
    P = {}
    u = max(rates["t1thk"]["unfinished"], rates["t1ver"]["unfinished"]); P["P6"] = {"unfinished_max_sampled": u, "holds": u <= 0.05}
    x, ci = d("t1ver", "t1thk", "U", A); P["P7"] = {"U_refuse_ver1_minus_thk1": [x, ci], "holds": x >= 0.05 and ci[0] > 0}
    rep = {f"{m}_{k1}_minus_{k2}": list(d(k1, k2, g, fn)) for k1, k2 in (("t1ver", "t1thk"), ("t1thk", "sgoff"), ("t1ver", "sgoff"), ("sgver", "sgthk"))
           for m, g, fn in (("H_acc", "H", C), ("U_refuse", "U", A), ("E_acc", "E", C), ("H_timid", "H", A))}
    rep["unfinished"] = {k: rates[k]["unfinished"] for k in R}
    rl = lambda k: float(np.median([len(R[k][i].get("reasoning") or "") for i in ids]))
    rep["median_reasoning_chars"] = {k: rl(k) for k in ("t1thk", "t1ver", "sgthk", "sgver")}
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(y, 3) for m, y in r.items()} for k, r in rates.items()}))
    for k, y in P.items(): print(k, "HOLDS" if y["holds"] else "does not hold", {m: y[m] for m in y if m != "holds"})
    for k, y in rep.items(): print("reported", k, y)


if __name__ == "__main__":
    main()
