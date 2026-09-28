#!/usr/bin/env python3
"""Registered analysis for PREREG_FLASHNEXT.md. Committed before any Flash-Next row existed.

Primary readout is the WRITTEN answer (grade from run_main.py): E/H accuracy (CORRECT), H timidity (ABSTAINED on H),
U refusal (ABSTAINED on U). TRUNCATED counts as neither correct nor refused. Paired differences by item, 95 %
percentile bootstrap over items (10,000 resamples, seed 20260928). Secondary: mean forced-slot P(UNKNOWN) per group.

Usage: analyze_flashnext.py [--q2 FNQ2] [--iq4 FNIQ4] [--q2x FNQ2X] [--ref C.A] [--ref-q2 UDQ2KXL] [--out RESULT_flashnext.json]
(The arm names are arguments so the script can be self-tested on stored 27B arms before Flash-Next data exists.)
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20260928, 10000


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
    ap.add_argument("--q2", default="FNQ2"); ap.add_argument("--iq4", default="FNIQ4"); ap.add_argument("--q2x", default="FNQ2X")
    ap.add_argument("--ref", default="C.A"); ap.add_argument("--ref-q2", default="UDQ2KXL")
    ap.add_argument("--out", default="RESULT_flashnext.json")
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    arms = {"q2": a.q2, "iq4": a.iq4, "q2x": a.q2x, "ref": a.ref, "ref_q2": a.ref_q2}
    R, hdr = {}, {}
    for k, arm in arms.items():
        try:
            hdr[k], R[k] = load(arm)
        except FileNotFoundError:
            print(f"missing arm {arm} ({k})", file=sys.stderr)
    ids = sorted(set(items).intersection(*[set(r) for r in R.values()]))
    grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    correct = lambda r: r["grade"] == "CORRECT"
    abstained = lambda r: r["grade"] == "ABSTAINED"
    out = {"arms": arms, "n": {g: len(v) for g, v in grp.items()}, "rates": {}, "slot": {}, "predictions": {}}
    for k, r in R.items():
        out["rates"][k] = {"E_acc": vec(r, grp["E"], correct).mean(), "H_acc": vec(r, grp["H"], correct).mean(),
                           "H_timid": vec(r, grp["H"], abstained).mean(), "U_refuse": vec(r, grp["U"], abstained).mean()}
        out["slot"][k] = {g: float(np.mean([r[i]["P_abs"] for i in grp[g]])) for g in "EHU"}
    rng = np.random.default_rng(SEED)

    def diff(k1, k2, g, fn):
        return boot(vec(R[k1], grp[g], fn) - vec(R[k2], grp[g], fn), rng)

    P = out["predictions"]
    if {"q2", "iq4"} <= R.keys():
        dh, dhci = diff("iq4", "q2", "H", correct); du, duci = diff("q2", "iq4", "U", abstained)
        P["P1"] = {"H_acc_iq4_minus_q2": [dh, dhci], "U_refuse_q2_minus_iq4": [du, duci],
                   "holds": dh >= 0.05 and dhci[0] > 0 and abs(du) <= 0.07}
    if {"iq4", "ref"} <= R.keys():
        d, ci = diff("iq4", "ref", "H", correct)
        P["P2"] = {"H_acc_iq4_minus_ref": [d, ci], "holds": d >= 0.05 and ci[0] > 0}
    if {"q2", "ref"} <= R.keys():
        d, ci = diff("q2", "ref", "H", correct)
        P["P3"] = {"H_acc_q2_minus_ref": [d, ci], "holds": d >= 0 and ci[0] > -0.05}
    if {"q2", "q2x"} <= R.keys():
        same = float(np.mean([R["q2"][i]["grade"] == R["q2x"][i]["grade"] for i in ids]))
        P["P4"] = {"same_grade_share": same, "holds": same >= 0.95}
    for k in ("q2", "iq4"):                              # reported, no prediction: U refusal vs the 27B Q8_0
        if {k, "ref"} <= R.keys():
            d, ci = diff(k, "ref", "U", abstained)
            out.setdefault("reported", {})[f"U_refuse_{k}_minus_ref"] = [d, ci]
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(v, 3) for m, v in r.items()} for k, r in out["rates"].items()}, indent=None))
    for k, v in P.items():
        print(k, "HOLDS" if v["holds"] else "does not hold", {m: v[m] for m in v if m != "holds"})


if __name__ == "__main__":
    main()
