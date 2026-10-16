#!/usr/bin/env python3
"""Registered analysis for PREREG_BOLT_THINK.md: Bolt thinking ON (BOLTTHINK) vs OFF (BOLT), paired by item.
Paired bootstrap 10,000, seed 20261018. Usage: analyze_bolt_think.py [--on BOLTTHINK] [--off BOLT] [--out RESULT_bolt_think.json]"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261018, 10000


def load(arm):
    rows = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.jsonl")]
    return {r["id"]: r for r in rows[1:] if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); idx = rng.integers(0, len(d), (NB, len(d))); m = d[idx].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--on", default="BOLTTHINK"); ap.add_argument("--off", default="BOLT")
    ap.add_argument("--out", default="RESULT_bolt_think.json"); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    ON, OFF = load(a.on), load(a.off)
    ids = sorted(set(items) & set(ON) & set(OFF)); grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
    C = lambda r: r["grade"] == "CORRECT"; A = lambda r: r["grade"] == "ABSTAINED"; T = lambda r: r["grade"] == "TRUNCATED"
    v = lambda R, g, fn: np.array([fn(R[i]) for i in grp[g]], float)
    rng = np.random.default_rng(SEED); d = lambda g, fn: boot(v(ON, g, fn) - v(OFF, g, fn), rng)
    rates = {k: {"E_acc": v(R, "E", C).mean(), "H_acc": v(R, "H", C).mean(), "H_timid": v(R, "H", A).mean(),
                 "U_refuse": v(R, "U", A).mean(), "truncated": float(np.mean([T(R[i]) for i in ids]))} for k, R in (("on", ON), ("off", OFF))}
    P = {}
    du, ci = d("U", A); P["P1"] = {"U_refuse_on_minus_off": [du, ci], "holds": du >= 0.15 and ci[0] > 0}
    dh, ci2 = d("H", C); P["P2"] = {"H_acc_on_minus_off": [dh, ci2], "holds": abs(dh) <= 0.07}
    P["P3"] = {"H_timid_on": rates["on"]["H_timid"], "holds": rates["on"]["H_timid"] <= 0.05}
    P["P4"] = {"truncated_on": rates["on"]["truncated"], "holds": rates["on"]["truncated"] <= 0.05}
    tok = lambda r: (r.get("completion_tokens") if r.get("completion_tokens") is not None else len(r.get("reasoning") or "") / 4)
    ta = [tok(ON[i]) for i in grp["U"] if A(ON[i])]; tw = [tok(ON[i]) for i in grp["U"] if ON[i]["grade"] == "WRONG"]
    P["P5"] = {"median_tokens_abstained": st.median(ta) if ta else None, "median_tokens_wrong": st.median(tw) if tw else None,
               "token_proxy": "completion_tokens if recorded, else reasoning chars / 4",
               "holds": bool(ta and tw and st.median(ta) > st.median(tw))}
    rep = {"E_acc_on_minus_off": list(d("E", C)),
           "per_template_U_refuse": {t: {k: float(np.mean([A(R[i]) for i in grp["U"] if items[i]["template"] == t]))
                                         for k, R in (("on", ON), ("off", OFF))} for t in sorted({items[i]["template"] for i in grp["U"]})},
           "reasoning_empty_on": sum(1 for i in ids if not ON[i].get("reasoning"))}
    pr = HERE / "raw" / "probe_think_BOLT.jsonl"
    if pr.exists():
        probe = [json.loads(l) for l in open(pr)]
        rep["probe_agreement"] = {"n": len(probe), "same_grade": sum(1 for r in probe if r["id"] in ON and ON[r["id"]]["grade"] == r["grade_on"])}
    out = {"rates": rates, "predictions": P, "reported": rep}
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print(json.dumps({k: {m: round(x, 3) for m, x in r.items()} for k, r in rates.items()}))
    for k, x in P.items(): print(k, "HOLDS" if x["holds"] else "does not hold", {m: x[m] for m in x if m != "holds"})
    for k, x in rep.items(): print("reported", k, x)


if __name__ == "__main__":
    main()
