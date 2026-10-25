#!/usr/bin/env python3
"""Registered analysis for PREREG_NANBEIGE.md: N33OFF / N33THK (Nanbeige4.3-33B Q8_0) vs the stored 27B Q8_0 (C.A),
SGOFF, Q36B, ORN and FLNT, paired by item. Paired bootstrap 10,000, seed 20261025. Usage: analyze_nanbeige.py"""
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
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="RESULT_nanbeige.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    R = {k: load(arm) for k, arm in (("n33", "N33OFF"), ("n33t", "N33THK"), ("ref", "C.A"), ("sgoff", "SGOFF"), ("q36b", "Q36B"),
                                     ("orn", "ORN"), ("flnt", "FLNT"))}
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()])); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"
    unfinished = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
    v = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda k1, k2, g, fn: boot(v(k1, g, fn) - v(k2, g, fn), rng)
    rates = {k: {"E_acc": v(k, "E", C).mean(), "H_acc": v(k, "H", C).mean(), "H_timid": v(k, "H", A).mean(),
                 "U_refuse": v(k, "U", A).mean(), "unfinished": float(np.mean([unfinished(R[k][i]) for i in ids]))} for k in R}
    P = {}
    x, ci = d("n33", "ref", "H", C); P["P1"] = {"H_acc_n33_minus_27b": [x, ci], "holds": x > 0}
    x, ci = d("n33", "ref", "U", A); P["P2"] = {"U_refuse_n33_minus_27b": [x, ci], "holds": x < 0}
    u = rates["n33t"]["unfinished"]; P["P3"] = {"unfinished_n33thk": u, "holds": u <= 0.05}
    rep = {f"{m}_{k1}_minus_{k2}": list(d(k1, k2, g, fn)) for k1, k2 in (("n33t", "n33"), ("n33", "sgoff"), ("n33", "q36b"), ("n33", "orn"), ("n33", "flnt"), ("n33t", "ref"))
           for m, g, fn in (("H_acc", "H", C), ("U_refuse", "U", A), ("E_acc", "E", C), ("H_timid", "H", A))}
    rep["median_reasoning_chars_n33thk"] = float(np.median([len(R["n33t"][i].get("reasoning") or "") for i in ids]))
    rep["reasoning_nonempty_n33off"] = sum(1 for i in ids if (R["n33"][i].get("reasoning") or ""))
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(y, 3) for m, y in r.items()} for k, r in rates.items()}))
    for k, y in P.items(): print(k, "HOLDS" if y["holds"] else "does not hold", {m: y[m] for m in y if m != "holds"})
    for k, y in rep.items(): print("reported", k, y)


if __name__ == "__main__":
    main()
