#!/usr/bin/env python3
"""Registered analysis for PREREG_BEAM_EFFORT.md: Beam at reasoning_effort max / low / high / medium (BEAMMAX, BEAMLOW,
BEAMHIGH, BEAMMED) against the stored minimal arm (BEAM), paired by item. Arms that were not run are skipped and
reported as missing. Paired bootstrap 10,000, seed 20261020.

Cost is measured two ways: total output characters per item (reasoning + content; the only measure the stored minimal
arm has) and, for the new arms, completion tokens and wall seconds per item from run_main.py --usage. Tokens transfer
to other hardware; seconds are this fleet's.

Usage: analyze_beam_effort.py [--arms BEAMMAX,BEAMLOW,BEAMHIGH,BEAMMED] [--base BEAM] [--raw DIR] [--out FILE]"""
import argparse, json, statistics as st
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
SEED, NB = 20261020, 10000
C = lambda r: r["grade"] == "CORRECT"
A = lambda r: r["grade"] == "ABSTAINED"
UNF = lambda r: r["grade"] == "TRUNCATED" or (r["grade"] == "INVALID" and r.get("finish") == "length")
CHARS = lambda r: len(r.get("reasoning") or "") + len(r.get("content") or "")


def load(raw, arm):
    p = raw / f"main_{arm}.jsonl"
    if not p.exists(): return None
    rows = [json.loads(l) for l in open(p)]
    return {r["id"]: r for r in rows if "id" in r}


def boot(d, rng):
    d = np.asarray(d, float); m = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
    return float(d.mean()), (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="BEAMMAX,BEAMLOW,BEAMHIGH,BEAMMED"); ap.add_argument("--base", default="BEAM")
    ap.add_argument("--raw", default=str(HERE / "raw")); ap.add_argument("--out", default="RESULT_beam_effort.json")
    a = ap.parse_args(); raw = Path(a.raw)
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    base = load(raw, a.base)
    R = {k: load(raw, k) for k in a.arms.split(",")}
    missing = [k for k, v in R.items() if v is None]; R = {k: v for k, v in R.items() if v}
    R[a.base] = base
    out = {"missing_arms": missing, "rates": {}, "cost": {}, "vs_base": {}, "predictions": {}, "flips": {}}
    rng = np.random.default_rng(SEED)
    for k, rows in R.items():
        ids = [i for i in items if i in rows and i in base]
        grp = {g: [i for i in ids if items[i]["arm"] == g] for g in "EHU"}
        v = lambda RR, g, fn: np.array([fn(RR[i]) for i in grp[g]], float)
        out["rates"][k] = {"n": len(ids), "E_acc": v(rows, "E", C).mean(), "H_acc": v(rows, "H", C).mean(),
                           "H_timid": v(rows, "H", A).mean(), "U_refuse": v(rows, "U", A).mean(),
                           "unfinished": float(np.mean([UNF(rows[i]) for i in ids]))}
        ch = [CHARS(rows[i]) for i in ids]
        cost = {"chars_median": st.median(ch), "chars_mean": st.mean(ch),
                "chars_by_group_median": {g: st.median([CHARS(rows[i]) for i in grp[g]]) for g in "EHU"}}
        tok = [((rows[i].get("gen_usage") or {}).get("completion_tokens")) for i in ids]
        if all(t is not None for t in tok):
            sec = [rows[i]["gen_elapsed_s"] for i in ids]
            nH = sum(C(rows[i]) for i in grp["H"])
            cost.update(tokens_median=st.median(tok), tokens_mean=st.mean(tok), tokens_p90=float(np.percentile(tok, 90)),
                        tokens_max=max(tok), seconds_median=st.median(sec), seconds_total_h=sum(sec) / 3600,
                        tokens_by_group_median={g: st.median([rows[i]["gen_usage"]["completion_tokens"] for i in grp[g]])
                                                for g in "EHU"},
                        chars_per_token=sum(ch) / sum(tok),
                        tokens_per_correct_hard=sum(rows[i]["gen_usage"]["completion_tokens"] for i in grp["H"]) / max(nH, 1))
        out["cost"][k] = cost
        if k == a.base: continue
        d = lambda g, fn: boot(v(rows, g, fn) - v(base, g, fn), rng)
        out["vs_base"][k] = {"H_acc": d("H", C), "U_refuse": d("U", A), "E_acc": d("E", C), "H_timid": d("H", A),
                             "chars_ratio_median": cost["chars_median"] / out["cost"].get(a.base, {}).get(
                                 "chars_median", st.median([CHARS(base[i]) for i in ids]))}
        out["flips"][k] = {"to_correct_or_refused": [i for i in ids if not (C(base[i]) or (items[i]["arm"] == "U" and A(base[i])))
                                                     and (C(rows[i]) or (items[i]["arm"] == "U" and A(rows[i])))],
                           "from_correct_or_refused": [i for i in ids if (C(base[i]) or (items[i]["arm"] == "U" and A(base[i])))
                                                       and not (C(rows[i]) or (items[i]["arm"] == "U" and A(rows[i])))]}
    bc = st.median([CHARS(base[i]) for i in base])
    P = {}
    hi = [k for k in R if k != a.base]
    P["P1"] = {"chars_ratio_median": {k: out["cost"][k]["chars_median"] / bc for k in hi},
               "holds_per_arm": {k: out["cost"][k]["chars_median"] / bc >= 1.3 for k in hi}}
    if "BEAMMAX" in R and "BEAMLOW" in R:
        r = out["cost"]["BEAMMAX"]["chars_median"] / out["cost"]["BEAMLOW"]["chars_median"]
        P["P2"] = {"max_over_low_chars_median": r, "holds": 1 / 1.5 <= r <= 1.5}
    if "BEAMMAX" in R:
        x, ci = out["vs_base"]["BEAMMAX"]["U_refuse"]; P["P3"] = {"U_refuse_max_minus_minimal": [x, ci], "holds": x >= -0.03 and ci[0] > -0.07}
        x, ci = out["vs_base"]["BEAMMAX"]["H_acc"]; P["P4"] = {"H_acc_max_minus_minimal": [x, ci], "holds": abs(x) <= 0.05}
    P["P5"] = {"unfinished": {k: out["rates"][k]["unfinished"] for k in hi},
               "holds_per_arm": {k: out["rates"][k]["unfinished"] <= 0.02 for k in hi}}
    out["predictions"] = P
    json.dump(out, open(HERE / a.out, "w"), indent=1, default=float)
    print("missing arms:", missing)
    for k, r in out["rates"].items(): print(k, {m: round(y, 3) for m, y in r.items()})
    for k, c in out["cost"].items(): print("cost", k, {m: (round(y, 2) if isinstance(y, float) else y) for m, y in c.items()})
    for k, y in out["vs_base"].items(): print("vs", a.base, k, y)
    for k, y in P.items(): print(k, y)


if __name__ == "__main__":
    main()
