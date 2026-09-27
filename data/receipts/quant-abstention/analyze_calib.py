#!/usr/bin/env python3
"""Offline per-file offset recalibration of the answer-slot abstention readout (PREREG_CALIB.md). Written and committed
before any real arm is scored with it; `--controls-only` runs the registered controls and never touches a real arm.

The question: the main campaign found the ranking of "I know" vs "I don't" preserved while the threshold moved per file.
Is that shift an OFFSET, i.e. does one logit bias b on the three UNKNOWN variants, fitted per file, return timidity (H),
confabulation (U) and easy-item timidity (E) to the Q8_0 values on every template at once?

Registered choices implemented here:
- The slot probabilities are full-softmax (post_sampling_probs false; the top 50 sum to < 1), so a logit bias b on the
  variants maps P_abs to P e^b / (1 - P + P e^b) exactly. A variant outside the stored top 50 has probability at most
  exp(last stored logprob): every analysis runs on the lower bound (as stored) and the upper bound (missing variants at
  that ceiling), and a verdict must hold under both.
- Fit: b on a grid [-10, 10] step 0.01 minimising max(|dtim_H|, |dcon_U|) against the ceiling on the fit fold (the
  verdict is a per-metric bound, so the objective is too). Ties go to the smallest |b|.
- Cross-fitting: stratified 2-fold (template x item arm), each item corrected with the b fitted on the other fold.
  Primary partition: seed 20260927. Stability: 1,000 further partitions.
- Verdict "fixed" (per arm, per bound):
  - pooled |dtim_H|, |dcon_U| and |dtim_E| <= 0.03 (points);
  - dtim_H and dcon_U paired t-intervals at 1 - 0.05/20 include 0 (10 labelled PTQ arms x 2 metrics);
  - every template cell (4 templates x {tim_H, con_U}) has |point| <= 0.10.
- H-offset: supported if >= 7 of the 10 labelled PTQ arms are fixed under both bounds; not supported if <= 3; partial
  otherwise.
- Controls:
  - identity: C.B against C.A must fit b = 0 in both folds with zero residuals;
  - positive: synthetic offset arms (C.A's logits + b0, b0 = +/-1.5) must be fixed with b = -b0;
  - negative: synthetic pivot-slope arms (logit -> c + a (logit - c), |log a| >= log 1.5) fitted to the pooled shifts
    of AD3XXS (timid) and AD2XS (confident). If the verdict passes them, "fixed" reads only as "correctable in the
    mean", not as "the shift is an offset".
- Secondary: the same verdict without operas; the OLS slope of the arm's slot logit on the ceiling's over H and U items
  (1 = offset); the full-sample b per arm (the number a live test would use).
"""
import argparse, json, math
from pathlib import Path
import numpy as np
from scipy import stats
from analyze_main import load, t_interval, T

HERE = Path(__file__).resolve().parent
VAR_IDS = (59322, 21024, 9496)
SEED = 20260927
N_REP = 1000
TOL, CELL_TOL = 0.03, 0.10
SHAPE = (0.8, 1.25)              # |log slope| < log 1.25
LABELLED = ["AD2XS", "AD3XXS", "AD3S", "UD3XXS", "AP2S", "APEXM", "AP3XXS", "APEXN", "EXL30", "EXL35"]
LEVEL = 1 - 0.05 / (2 * len(LABELLED))
GRID = np.round(np.arange(-1000, 1001) / 100, 2)


def bounds(row):
    top = row["slot_top"]
    present = {t[0] for t in top}
    miss = sum(v not in present for v in VAR_IDS)
    return row["P_abs"], min(row["P_abs"] + miss * math.exp(top[-1][2]), 1.0)


def shift(p, b):
    e = np.exp(b)
    return p * e / (1 - p + p * e)


def logit(p):
    p = np.clip(p, 1e-7, 1 - 1e-7)
    return np.log(p) - np.log1p(-p)


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


class Data:
    def __init__(self, items):
        self.ids = sorted(items)
        self.tmpl = np.array([items[i]["template"] for i in self.ids])
        self.arm = np.array([items[i]["arm"] for i in self.ids])
        self.cells = [(t, a) for t in T for a in "EHU"]

    def vec(self, R, which):
        return np.array([bounds(R[i])[which] for i in self.ids])

    def partitions(self, n, seed, keep=None):
        """n stratified 2-fold partitions: a boolean mask per partition, True = fold 0."""
        rng = np.random.default_rng(seed)
        keep = np.ones(len(self.ids), bool) if keep is None else keep
        out = np.zeros((n, len(self.ids)), bool)
        for t, a in self.cells:
            idx = np.flatnonzero((self.tmpl == t) & (self.arm == a) & keep)
            if not len(idx):
                continue
            for r in range(n):
                perm = rng.permutation(idx)
                out[r, perm[: len(idx) // 2]] = True
        return out


def fit_b(S, pc, h, u):
    """S: (grid, items) shifted arm values; h, u: masks of the fit fold's H and U items. Returns b."""
    dt = S[:, h].mean(1) - pc[h].mean()
    dc = pc[u].mean() - S[:, u].mean(1)
    obj = np.maximum(np.abs(dt), np.abs(dc)) + 1e-12 * np.abs(GRID)
    return float(GRID[int(np.argmin(obj))])


def crossfit(D, pa, pc, fold0, keep, S=None):
    """Corrected arm values (each item with the other fold's b) and the two b's. S: the arm's shift table, if cached."""
    S = shift(pa[None, :], GRID[:, None]) if S is None else S
    H, U = (D.arm == "H") & keep, (D.arm == "U") & keep
    bs, out = [], pa.copy()
    for f in (fold0, ~fold0):
        b = fit_b(S, pc, H & f, U & f)
        bs.append(b)
        test = ~f & keep
        out[test] = shift(pa[test], b)
    return out, bs


def metrics(D, pa, pc, keep, level=None):
    H, U, E = (D.arm == "H") & keep, (D.arm == "U") & keep, (D.arm == "E") & keep
    m = {"tim_H": float((pa[H] - pc[H]).mean()), "con_U": float((pc[U] - pa[U]).mean()),
         "tim_E": float((pa[E] - pc[E]).mean())}
    if level:
        m["tim_H_iv"] = t_interval(pa[H] - pc[H], level)[1]
        m["con_U_iv"] = t_interval(pc[U] - pa[U], level)[1]
    m["cells"] = {}
    for t in T:
        tk = D.tmpl == t
        if (H & tk).any():
            m["cells"][t] = {"tim_H": float((pa[H & tk] - pc[H & tk]).mean()),
                             "con_U": float((pc[U & tk] - pa[U & tk]).mean())}
    return m


def fixed(m):
    ok_pool = all(abs(m[k]) <= TOL for k in ("tim_H", "con_U", "tim_E"))
    ok_iv = all(iv[0] <= 0 <= iv[1] for iv in (m["tim_H_iv"], m["con_U_iv"])) if "tim_H_iv" in m else True
    ok_cells = all(abs(v) <= CELL_TOL for c in m["cells"].values() for v in c.values())
    return bool(ok_pool and ok_iv and ok_cells)


def slope(D, pa, pc):
    """OLS of the arm's slot logit on the ceiling's, over H and U items whose ceiling P is in [0.01, 0.99] (selection on
    x only, so the slope is not biased by it; it drops the extremes, where the top-50 bounds and clipping bite)."""
    m = ((D.arm == "H") | (D.arm == "U")) & (pc >= 0.01) & (pc <= 0.99)
    x, y = logit(pc[m]), logit(pa[m])
    X = np.column_stack([np.ones_like(x), x])
    beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    s2 = float(res[0]) / (len(x) - 2) if len(res) else 0.0
    se = math.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    h = stats.t.ppf(1 - (1 - LEVEL) / 2, len(x) - 2) * se
    lo, hi = float(beta[1]) - h, float(beta[1]) + h
    shape = "offset-shaped" if SHAPE[0] <= lo and hi <= SHAPE[1] else \
            "slope-changed" if hi < SHAPE[0] or lo > SHAPE[1] else "inconclusive"
    return {"slope": float(beta[1]), "slope_se": se, "iv": (lo, hi), "intercept": float(beta[0]), "n": int(m.sum()),
            "shape": shape}


def evaluate(D, pa_by_bound, pc_by_bound, parts, keep):
    """pa_by_bound / pc_by_bound: {"lo": vec, "hi": vec}. Primary = parts[0]."""
    out = {}
    for bd in pa_by_bound:
        pa, pc = pa_by_bound[bd], pc_by_bound[bd]
        corr, bs = crossfit(D, pa, pc, parts[0], keep)
        before = metrics(D, pa, pc, keep, LEVEL)
        after = metrics(D, corr, pc, keep, LEVEL)
        out[bd] = {"b_folds": bs, "before": before, "after": after, "fixed": fixed(after)}
    out["fixed_both"] = all(out[bd]["fixed"] for bd in pa_by_bound)
    return out


def stability(D, pa_by_bound, pc_by_bound, parts, keep, primary):
    agree, bmed = 0, {bd: [] for bd in pa_by_bound}
    S = {bd: shift(pa_by_bound[bd][None, :], GRID[:, None]) for bd in pa_by_bound}
    for r in range(1, len(parts)):
        v = True
        for bd in pa_by_bound:
            corr, bs = crossfit(D, pa_by_bound[bd], pc_by_bound[bd], parts[r], keep, S[bd])
            v &= fixed(metrics(D, corr, pc_by_bound[bd], keep, LEVEL))
            bmed[bd] += bs
        agree += v == primary
    return {"agree_frac": agree / (len(parts) - 1), "b_median": {bd: float(np.median(x)) for bd, x in bmed.items()}}


def full_b(D, pa, pc):
    S = shift(pa[None, :], GRID[:, None])
    return fit_b(S, pc, D.arm == "H", D.arm == "U")


def synth_slope(D, pc, target):
    """Pivot-slope arm from the ceiling's upper-bound values closest to target (dtim_H, dcon_U), |log a| >= log 1.5."""
    H, U = D.arm == "H", D.arm == "U"
    x = logit(pc)
    best = None
    for a in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 1.5, 1.75, 2.0, 2.25, 2.5]:
        for c in np.round(np.arange(-80, 81) / 10, 1):
            p = sigmoid(c + a * (x - c))
            d = ((p[H] - pc[H]).mean(), (pc[U] - p[U]).mean())
            err = math.hypot(d[0] - target[0], d[1] - target[1])
            if best is None or err < best[0]:
                best = (err, a, float(c), p, d)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls-only", action="store_true")
    ap.add_argument("--reps", type=int, default=N_REP)
    a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
    reg = {x["arm"]: x for x in json.load(open(HERE / "arms_main.json"))["arms"]}
    D = Data(items)
    all_ = np.ones(len(D.ids), bool)
    no_op = D.tmpl != "opera"
    parts = D.partitions(a.reps + 1, SEED)
    parts_no = D.partitions(a.reps + 1, SEED, no_op)
    ceil = {ln: load(HERE / "raw" / f"main_C.{ln}.jsonl")[1] for ln in "AB"}
    pc = {ln: {bd: D.vec(ceil[ln], j) for j, bd in enumerate(("lo", "hi"))} for ln in "AB"}
    out = {"level": LEVEL, "tol": TOL, "cell_tol": CELL_TOL, "reps": a.reps, "controls": {}, "arms": {}}

    # controls
    idn = evaluate(D, pc["B"], pc["A"], parts, all_)
    out["controls"]["identity_CB_vs_CA"] = {
        "b_folds": {bd: idn[bd]["b_folds"] for bd in ("lo", "hi")},
        "max_abs_residual": max(abs(idn[bd]["after"][k]) for bd in ("lo", "hi") for k in ("tim_H", "con_U", "tim_E")),
        "pass": all(idn[bd]["b_folds"] == [0.0, 0.0] for bd in ("lo", "hi")) and idn["fixed_both"]}
    hiC = pc["A"]["hi"]
    for b0 in (1.5, -1.5):
        syn = shift(hiC, b0)
        r = evaluate(D, {"hi": syn}, {"hi": hiC}, parts, all_)
        out["controls"][f"offset_{b0:+.1f}"] = {"b_folds": r["hi"]["b_folds"], "before": r["hi"]["before"],
                                               "after": r["hi"]["after"], "fixed": r["fixed_both"],
                                               "pass": r["fixed_both"] and all(abs(b + b0) < 0.011 for b in r["hi"]["b_folds"])}
    for name, target in (("slope_timid_like_AD3XXS", (0.121, -0.112)), ("slope_confident_like_AD2XS", (-0.028, 0.213))):
        err, sa, sc, syn, d = synth_slope(D, hiC, target)
        r = evaluate(D, {"hi": syn}, {"hi": hiC}, parts, all_)
        out["controls"][name] = {"a": sa, "c": sc, "target": target, "achieved": d, "fit_err": err,
                                 "b_folds": r["hi"]["b_folds"], "after": r["hi"]["after"], "fixed": r["fixed_both"],
                                 "slope": slope(D, syn, hiC)}
    out["controls"]["identity_CB_vs_CA"]["slope"] = slope(D, pc["B"]["hi"], hiC)
    for b0 in (1.5, -1.5):
        out["controls"][f"offset_{b0:+.1f}"]["slope"] = slope(D, shift(hiC, b0), hiC)
    for k, v in out["controls"].items():
        print(f"control {k:28s} b {v.get('b_folds')}  fixed {v.get('fixed', v.get('pass'))}  pass {v.get('pass', '-')}"
              f"  slope {v['slope']['slope']:.3f} {v['slope']['shape']}"
              + (f"  a {v['a']} c {v['c']} achieved {tuple(round(x, 3) for x in v['achieved'])}" if "a" in v else ""))
    if a.controls_only:
        json.dump(out, open(HERE / "RESULT_calib_CONTROLS.json", "w"), indent=1, default=float)
        return

    for arm in reg:
        if arm == "C":
            continue
        hdr, R = load(HERE / "raw" / f"main_{arm}.jsonl")
        ln = hdr["meta"]["lane"]
        pa = {bd: D.vec(R, j) for j, bd in enumerate(("lo", "hi"))}
        r = evaluate(D, pa, pc[ln], parts, all_)
        rn = evaluate(D, pa, pc[ln], parts_no, no_op)
        st = stability(D, pa, pc[ln], parts, all_, r["fixed_both"])
        out["arms"][arm] = {"family": reg[arm]["family"], "category": reg[arm]["category"],
                            "scored_bpw": reg[arm]["scored_bpw"], "lane": ln, "labelled": arm in LABELLED,
                            **r, "stability": st, "without_opera": {"fixed_both": rn["fixed_both"],
                                                                    **{bd: rn[bd] for bd in ("lo", "hi")}},
                            "slope_hi": slope(D, pa["hi"], pc[ln]["hi"]),
                            "b_full": {bd: full_b(D, pa[bd], pc[ln][bd]) for bd in ("lo", "hi")}}
    verdict = lambda n: "supported" if n >= 7 else "not supported" if n <= 3 else "partial"
    lab = [x for x in LABELLED if out["arms"][x]["fixed_both"]]
    out["H_fix"] = {"fixed": lab, "n": len(lab), "of": len(LABELLED), "verdict": verdict(len(lab))}
    sh = [x for x in LABELLED if out["arms"][x]["slope_hi"]["shape"] == "offset-shaped"]
    out["H_offset_shape"] = {"offset_shaped": sh, "n": len(sh), "of": len(LABELLED), "verdict": verdict(len(sh))}
    json.dump(out, open(HERE / "RESULT_calib.json", "w"), indent=1, default=float)
    for arm, v in out["arms"].items():
        b, af = v["hi"]["before"], v["hi"]["after"]
        worst = max(abs(x) for c in af["cells"].values() for x in c.values())
        print(f"{arm:8s} b {v['hi']['b_folds']} full {v['b_full']['hi']:+.2f} | before tim {b['tim_H']:+.3f} con {b['con_U']:+.3f}"
              f" E {b['tim_E']:+.3f} | after tim {af['tim_H']:+.3f} con {af['con_U']:+.3f} E {af['tim_E']:+.3f}"
              f" cell {worst:.3f} | fixed lo/hi {v['lo']['fixed']}/{v['hi']['fixed']} noop {v['without_opera']['fixed_both']}"
              f" stab {v['stability']['agree_frac']:.2f} slope {v['slope_hi']['slope']:.2f} {v['slope_hi']['shape']}")
    print("H-fix:", out["H_fix"]); print("H-offset-shape:", out["H_offset_shape"])


if __name__ == "__main__":
    main()
