#!/usr/bin/env python3
"""Registered analysis for PREREG_SAGE.md: SGOFF / SGTHK / SGVER (Sage-A1.5 Q8_0) and Q36B (Qwen3.6-35B-A3B Q6_K) vs the
stored 27B Q8_0 (C.A), ORN and FLNT, paired by item. Paired bootstrap 10,000, seed 20261024. Usage: analyze_sage.py"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261024, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="RESULT_sage.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    R = {k: load(arm) for k, arm in (("sgoff", "SGOFF"), ("q36b", "Q36B"), ("sgthk", "SGTHK"), ("sgver", "SGVER"),
                                     ("ref", "C.A"), ("orn", "ORN"), ("flnt", "FLNT"))}
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()])); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"
    unfinished = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
    v = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda k1, k2, g, fn: boot(v(k1, g, fn) - v(k2, g, fn), rng)
    rates = {k: {"E_acc": v(k, "E", C).mean(), "H_acc": v(k, "H", C).mean(), "H_timid": v(k, "H", A).mean(),
                 "U_refuse": v(k, "U", A).mean(), "unfinished": float(np.mean([unfinished(R[k][i]) for i in ids]))} for k in R}
    P = {}
    x, ci = d("sgoff", "ref", "H", C); P["P1"] = {"H_acc_sgoff_minus_27b": [x, ci], "holds": x <= -0.05 and ci[1] < 0}
    x, ci = d("sgoff", "ref", "U", A); P["P2"] = {"U_refuse_sgoff_minus_27b": [x, ci], "holds": x < 0}
    x, ci = d("sgoff", "q36b", "H", C); P["P3"] = {"H_acc_sgoff_minus_base": [x, ci], "holds": abs(x) <= 0.05}
    x, ci = d("sgver", "sgthk", "U", A); P["P4"] = {"U_refuse_ver_minus_thk": [x, ci], "holds": x >= 0.05 and ci[0] > 0}
    u = max(rates["sgthk"]["unfinished"], rates["sgver"]["unfinished"]); P["P5"] = {"unfinished_max_thinking": u, "holds": u <= 0.05}
    rep = {f"{m}_{k1}_minus_{k2}": list(d(k1, k2, g, fn)) for k1, k2 in (("sgoff", "q36b"), ("sgver", "sgthk"), ("sgthk", "sgoff"),
           ("sgoff", "orn"), ("sgoff", "flnt"), ("q36b", "ref")) for m, g, fn in (("H_acc", "H", C), ("U_refuse", "U", A), ("E_acc", "E", C), ("H_timid", "H", A))}
    rl = lambda k: float(np.median([len(R[k][i].get("reasoning") or "") for i in ids]))
    rep["median_reasoning_chars"] = {k: rl(k) for k in ("sgthk", "sgver")}
    rep["reasoning_nonempty_thinking_off"] = {k: sum(1 for i in ids if (R[k][i].get("reasoning") or "")) for k in ("sgoff", "q36b")}
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(y, 3) for m, y in r.items()} for k, r in rates.items()}))
    for k, y in P.items(): print(k, "HOLDS" if y["holds"] else "does not hold", {m: y[m] for m in y if m != "holds"})
    for k, y in rep.items(): print("reported", k, y)


if __name__ == "__main__":
    main()
