#!/usr/bin/env python3
"""Registered analysis for PREREG_SUPERVL.md, derived from analyze_bolt.py. Committed before any Super VL row existed.

Primary readout is the WRITTEN answer (grade from run_main.py): E/H accuracy (CORRECT), H timidity (ABSTAINED on H),
U refusal (ABSTAINED on U). TRUNCATED counts as neither correct nor refused. Paired differences by item, 95 %
percentile bootstrap over items (10,000 resamples, seed 20261016).

Usage: analyze_supervl.py [--sv SVQ2] [--fn FNQ2] [--bolt BOLT] [--ref C.A] [--out RESULT_supervl.json]
(Arm names are arguments so the script can be self-tested on stored arms before Super VL data exists.)
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261016, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return rows[0], {r["id"]: r for r in rows[1:] if "id" in r}


def vec(R, ids, fn):
    return np.array([fn(R[i]) for i in ids], float)


def boot(d, rng):
    d = np.asarray(d, float)
    idx = rng.integers(0, len(d), (NB, len(d)))
    m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sv", default="SVQ2"); ap.add_argument("--fn", default="FNQ2"); ap.add_argument("--bolt", default="BOLT")
    ap.add_argument("--ref", default="C.A"); ap.add_argument("--out", default="RESULT_supervl.json")
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    arms = {"sv": a.sv, "fn": a.fn, "bolt": a.bolt, "ref": a.ref}
    R, hdr = {}, {}
    for k, arm in arms.items():
        hdr[k], R[k] = load(arm)
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()]))
    grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    correct = lambda r: r["grade"] == "CORRECT"
    abstained = lambda r: r["grade"] == "ABSTAINED"
    trunc = lambda r: r["grade"] == "TRUNCATED"
    out = {"arms": arms, "n": {g: len(v) for g, v in grp.items()}, "rates": {}, "predictions": {}, "reported": {}}
    for k, r in R.items():
        out["rates"][k] = {"E_acc": vec(r, grp["E"], correct).mean(), "H_acc": vec(r, grp["H"], correct).mean(),
                           "H_timid": vec(r, grp["H"], abstained).mean(), "U_refuse": vec(r, grp["U"], abstained).mean(),
                           "truncated": vec(r, ids, trunc).mean()}
    rng = np.random.default_rng(SEED)

    def diff(k1, k2, g, fn):
        return boot(vec(R[k1], grp[g], fn) - vec(R[k2], grp[g], fn), rng)

    P = out["predictions"]
    d, ci = diff("sv", "fn", "H", correct); P["P1"] = {"H_acc_sv_minus_fn": [d, ci], "holds": d <= -0.05 and ci[1] < 0}
    d, ci = diff("sv", "fn", "U", abstained); P["P2"] = {"U_refuse_sv_minus_fn": [d, ci], "holds": d <= -0.10 and ci[1] < 0}
    d, ci = diff("sv", "bolt", "H", correct); P["P3"] = {"H_acc_sv_minus_bolt": [d, ci], "holds": d >= 0.10 and ci[0] > 0}
    d, ci = diff("sv", "bolt", "U", abstained); P["P4"] = {"U_refuse_sv_minus_bolt": [d, ci], "holds": d >= 0.10 and ci[0] > 0}
    t = out["rates"]["sv"]["truncated"]; P["P5"] = {"truncated_share": t, "holds": t <= 0.02}
    out["reported"]["H_acc_sv_minus_ref"] = list(diff("sv", "ref", "H", correct))
    out["reported"]["U_refuse_sv_minus_ref"] = list(diff("sv", "ref", "U", abstained))
    out["reported"]["E_acc_sv_minus_fn"] = list(diff("sv", "fn", "E", correct))
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(v, 3) for m, v in r.items()} for k, r in out["rates"].items()}, indent=None))
    for k, v in P.items():
        print(k, "HOLDS" if v["holds"] else "does not hold", {m: v[m] for m in v if m != "holds"})
    for k, v in out["reported"].items():
        print("reported", k, v)


if __name__ == "__main__":
    main()
