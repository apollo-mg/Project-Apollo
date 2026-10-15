#!/usr/bin/env python3
"""Registered analysis for PREREG_BOLT.md, derived from analyze_flashnext.py. Committed before any Bolt row existed.

Primary readout is the WRITTEN answer (grade from run_main.py): E/H accuracy (CORRECT), H timidity (ABSTAINED on H),
U refusal (ABSTAINED on U). TRUNCATED counts as neither correct nor refused. Paired differences by item, 95 %
percentile bootstrap over items (10,000 resamples, seed 20261015).

Usage: analyze_bolt.py [--bolt BOLT] [--fn FNQ2] [--ref C.A] [--out RESULT_bolt.json]
(Arm names are arguments so the script can be self-tested on stored arms before Bolt data exists.)
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261015, 10000


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
    ap.add_argument("--bolt", default="BOLT"); ap.add_argument("--fn", default="FNQ2"); ap.add_argument("--ref", default="C.A")
    ap.add_argument("--out", default="RESULT_bolt.json")
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    arms = {"bolt": a.bolt, "fn": a.fn, "ref": a.ref}
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
    d, ci = diff("bolt", "fn", "H", correct); P["P1"] = {"H_acc_bolt_minus_fn": [d, ci], "holds": d <= -0.05 and ci[1] < 0}
    d, ci = diff("bolt", "ref", "H", correct); P["P2"] = {"H_acc_bolt_minus_ref": [d, ci], "holds": d >= 0 and ci[0] > -0.05}
    d, ci = diff("bolt", "ref", "U", abstained); P["P3"] = {"U_refuse_bolt_minus_ref": [d, ci], "holds": d >= 0 and ci[0] > -0.07}
    t = out["rates"]["bolt"]["truncated"]; P["P4"] = {"truncated_share": t, "holds": t <= 0.02}
    out["reported"]["U_refuse_bolt_minus_fn"] = list(diff("bolt", "fn", "U", abstained))
    out["reported"]["E_acc_bolt_minus_ref"] = list(diff("bolt", "ref", "E", correct))
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(v, 3) for m, v in r.items()} for k, r in out["rates"].items()}, indent=None))
    for k, v in P.items():
        print(k, "HOLDS" if v["holds"] else "does not hold", {m: v[m] for m in v if m != "holds"})
    for k, v in out["reported"].items():
        print("reported", k, v)


if __name__ == "__main__":
    main()
