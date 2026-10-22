#!/usr/bin/env python3
"""Registered analysis for PREREG_FLINT.md: FLNT (thinking off) and FLTK (thinking on) vs stored BEAM, SVNV, FNQ2, BOLT
and the 27B Q8_0 (C.A), paired by item. Paired bootstrap 10,000, seed 20261021. Usage: analyze_flint.py [--out ...]"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261021, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="RESULT_flint.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    R = {k: load(arm) for k, arm in (("flnt", "FLNT"), ("fltk", "FLTK"), ("beam", "BEAM"), ("sv", "SVNV"),
                                     ("fn", "FNQ2"), ("bolt", "BOLT"), ("ref", "C.A"))}
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()])); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"
    unfinished = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
    v = lambda k, g, fn: np.array([fn(R[k][i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda k1, k2, g, fn: boot(v(k1, g, fn) - v(k2, g, fn), rng)
    rates = {k: {"E_acc": v(k, "E", C).mean(), "H_acc": v(k, "H", C).mean(), "H_timid": v(k, "H", A).mean(),
                 "U_refuse": v(k, "U", A).mean(), "unfinished": float(np.mean([unfinished(R[k][i]) for i in ids]))} for k in R}
    P = {}
    x, ci = d("flnt", "ref", "H", C); P["P1"] = {"H_acc_flnt_minus_27b": [x, ci], "holds": x <= 0}
    x, ci = d("flnt", "sv", "U", A); P["P2"] = {"U_refuse_flnt_minus_sv": [x, ci], "holds": x <= -0.10 and ci[1] < 0}
    x, ci = d("fltk", "flnt", "U", A); P["P3"] = {"U_refuse_fltk_minus_flnt": [x, ci], "holds": x >= 0.05 and ci[0] > -0.05}
    u = max(rates["flnt"]["unfinished"], rates["fltk"]["unfinished"]); P["P4"] = {"max_unfinished_share": u, "holds": u <= 0.02}
    rep = {f"{m}_{a1}_minus_{k}": list(d(a1, k, g, fn)) for a1 in ("flnt", "fltk") for k in ("beam", "sv", "fn", "bolt", "ref")
           for m, g, fn in (("H_acc", "H", C), ("U_refuse", "U", A), ("E_acc", "E", C))}
    rep["H_acc_fltk_minus_flnt"] = list(d("fltk", "flnt", "H", C))
    rl = [len(R["fltk"][i].get("reasoning") or "") for i in ids]
    rep["fltk_median_reasoning_chars"] = st.median(rl); rep["fltk_reasoning_empty"] = sum(1 for x in rl if x == 0)
    rep["flnt_reasoning_nonempty"] = sum(1 for i in ids if (R["flnt"][i].get("reasoning") or ""))
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(y, 3) for m, y in r.items()} for k, r in rates.items()}))
    for k, y in P.items(): print(k, "HOLDS" if y["holds"] else "does not hold", {m: y[m] for m in y if m != "holds"})
    for k, y in rep.items(): print("reported", k, y)


if __name__ == "__main__":
    main()
