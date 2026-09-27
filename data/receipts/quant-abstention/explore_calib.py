#!/usr/bin/env python3
"""EXPLORATORY follow-ups to RESULT_CALIB.md (written after the registered result was committed; nothing here changes
a registered verdict or label).

1. What a slope below 1 is. Over the same items as analyze_calib.slope (H+U, Q8_0's P in [0.01, 0.99]), report the
   Pearson r of the two logits, the SD ratio (arm / Q8_0) and the forward slope (= r x SD ratio):
   - compression (the arm's logits are a scaled copy): SD ratio ~ slope, r high;
   - weaker agreement (the arm keeps only part of Q8_0's item-level variation): SD ratio ~ 1, slope ~ r.
   The slope is also refitted on items where all three UNKNOWN variants are in both top 50s (exact values, no
   truncation bound).
2. The greedy decision. At temperature 0 the slot abstains iff the best variant's logit beats every other token:
   with a bias b, iff b > N - V (N = best non-variant logprob, V = best variant logprob). A monotone affine map of the
   logit is undone exactly by an offset here, so the slope synthetics are no control for this readout; only template
   heterogeneity and item noise can fail it. The same cross-fit, tolerances and cell rule as analyze_calib, on the
   abstain RATES (H: over-abstention, U: answering an invented item, E: refusing an easy item).
"""
import json, math
from pathlib import Path
import numpy as np
from analyze_calib import (Data, SEED, TOL, CELL_TOL, LEVEL, LABELLED, GRID, VAR_IDS, bounds, logit)
from analyze_main import load, t_interval, T

HERE = Path(__file__).resolve().parent


def slope_diag(D, pa, pc, mask=None):
    m = ((D.arm == "H") | (D.arm == "U")) & (pc >= 0.01) & (pc <= 0.99)
    if mask is not None:
        m &= mask
    x, y = logit(pc[m]), logit(pa[m])
    r = float(np.corrcoef(x, y)[0, 1])
    sdr = float(np.std(y, ddof=1) / np.std(x, ddof=1))
    return {"n": int(m.sum()), "r": r, "sd_ratio": sdr, "slope": r * sdr}


def all_present(R, ids):
    return np.array([all(v in {t[0] for t in R[i]["slot_top"]} for v in VAR_IDS) for i in ids])


def tau(R, ids, bound):
    """Per item: the bias above which the slot's argmax is an UNKNOWN variant (N - V)."""
    out = []
    for i in ids:
        top = R[i]["slot_top"]
        var = [t[2] for t in top if t[0] in VAR_IDS]
        miss = len(VAR_IDS) - len(var)
        if bound == "hi" and miss:
            var.append(top[-1][2])
        N = max(t[2] for t in top if t[0] not in VAR_IDS)
        out.append(N - max(var) if var else math.inf)
    return np.array(out)


def dec_metrics(D, da, dc, keep, level=None):
    """da, dc: 0/1 abstain decisions (arm after bias, ceiling)."""
    H, U, E = (D.arm == "H") & keep, (D.arm == "U") & keep, (D.arm == "E") & keep
    m = {"tim_H": float((da[H] - dc[H]).mean()), "con_U": float((dc[U] - da[U]).mean()),
         "tim_E": float((da[E] - dc[E]).mean()), "agree": float((da[keep] == dc[keep]).mean())}
    if level:
        m["tim_H_iv"] = t_interval(da[H] - dc[H], level)[1]
        m["con_U_iv"] = t_interval(dc[U] - da[U], level)[1]
    m["cells"] = {t: {"tim_H": float((da[H & (D.tmpl == t)] - dc[H & (D.tmpl == t)]).mean()),
                      "con_U": float((dc[U & (D.tmpl == t)] - da[U & (D.tmpl == t)]).mean())}
                  for t in T if (H & (D.tmpl == t)).any()}
    return m


def dec_fixed(m):
    ok = all(abs(m[k]) <= TOL for k in ("tim_H", "con_U", "tim_E"))
    ok &= all(iv[0] <= 0 <= iv[1] or (iv[0] != iv[0]) for iv in (m["tim_H_iv"], m["con_U_iv"]))
    ok &= all(abs(v) <= CELL_TOL for c in m["cells"].values() for v in c.values())
    return bool(ok)


def dec_crossfit(D, ta, dc, fold0, keep):
    A = (ta[None, :] < GRID[:, None]).astype(float)           # (grid, items) decisions under each b
    H, U = (D.arm == "H") & keep, (D.arm == "U") & keep
    out, bs = np.zeros(len(ta)), []
    for f in (fold0, ~fold0):
        h, u = H & f, U & f
        obj = np.maximum(np.abs(A[:, h].mean(1) - dc[h].mean()), np.abs(dc[u].mean() - A[:, u].mean(1)))
        b = float(GRID[int(np.argmin(obj + 1e-12 * np.abs(GRID)))])
        bs.append(b)
        test = ~f & keep
        out[test] = (ta[test] < b).astype(float)
    return out, bs


def main():
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    reg = {x["arm"]: x for x in json.load(open(HERE / "arms_main.json"))["arms"]}
    D = Data(items)
    all_ = np.ones(len(D.ids), bool)
    parts = D.partitions(1001, SEED)       # identical draws to analyze_calib (N_REP + 1), so partition 0 is its primary
    ceil = {ln: load(HERE / "raw" / f"main_C.{ln}.jsonl")[1] for ln in "AB"}
    out = {"note": "EXPLORATORY; see the docstring", "arms": {}}
    for arm in reg:
        if arm == "C":
            continue
        hdr, R = load(HERE / "raw" / f"main_{arm}.jsonl")
        C = ceil[hdr["meta"]["lane"]]
        pa, pc = D.vec(R, 1), D.vec(C, 1)
        both = all_present(R, D.ids) & all_present(C, D.ids)
        pa_lo, pc_lo = D.vec(R, 0), D.vec(C, 0)
        res = {"slope_diag": slope_diag(D, pa, pc), "slope_diag_all_variants": slope_diag(D, pa_lo, pc_lo, both)}
        for bd in ("lo", "hi"):
            ta, tc = tau(R, D.ids, bd), tau(C, D.ids, bd)
            dc = (tc < 0).astype(float)
            da0 = (ta < 0).astype(float)
            corr, bs = dec_crossfit(D, ta, dc, parts[0], all_)
            before, after = dec_metrics(D, da0, dc, all_, LEVEL), dec_metrics(D, corr, dc, all_, LEVEL)
            res[f"decision_{bd}"] = {"b_folds": bs, "before": before, "after": after, "fixed": dec_fixed(after)}
        res["decision_fixed_both"] = res["decision_lo"]["fixed"] and res["decision_hi"]["fixed"]
        out["arms"][arm] = res
    json.dump(out, open(HERE / "EXPLORE_calib.json", "w"), indent=1, default=float)
    print("arm       slope   r    SDratio | all-variants n slope r SDratio | decision b      before tim/con/E      after tim/con/E  agree b->a  worst cell  fixed")
    for arm, v in out["arms"].items():
        s, s2, d = v["slope_diag"], v["slope_diag_all_variants"], v["decision_hi"]
        b, a = d["before"], d["after"]
        w = max(((t, k, x) for t, c in a["cells"].items() for k, x in c.items()), key=lambda z: abs(z[2]))
        print(f"{'*' if arm in LABELLED else ' '}{arm:8s} {s['slope']:.2f} {s['r']:.2f} {s['sd_ratio']:.2f} | {s2['n']:3d} {s2['slope']:.2f} {s2['r']:.2f} {s2['sd_ratio']:.2f}"
              f" | {d['b_folds']} {b['tim_H']:+.2f}/{b['con_U']:+.2f}/{b['tim_E']:+.2f} -> {a['tim_H']:+.2f}/{a['con_U']:+.2f}/{a['tim_E']:+.2f}"
              f"  {b['agree']:.2f}->{a['agree']:.2f}  {w[0][:3]}.{w[1][:3]} {w[2]:+.2f}  {v['decision_lo']['fixed']}/{d['fixed']}")
    lab = [x for x in LABELLED if out["arms"][x]["decision_fixed_both"]]
    print("decision-level fixed (labelled):", len(lab), lab)


if __name__ == "__main__":
    main()
