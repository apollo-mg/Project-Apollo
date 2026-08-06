#!/usr/bin/env python3
"""Phase 1 analysis: paired K=5 comparison of GLM-4.7-Flash base vs cerebras REAP-23B.

Reports mean and RANGE across replicates, never a single run (standard §7), and puts the
within-arm range next to the between-arm delta so the margin is visible rather than asserted.
Both `raw` and `penalized` are reported because pruning may convert refusals into hallucinations,
which moves penalized while leaving raw nearly flat.
"""
import json, sys, glob, statistics as st
from collections import defaultdict

sys.path.insert(0, "/home/mark/ikp_glm")
from ikp_score import grade, HALLUCINATION_PENALTY

TIERS = ["T1", "T2", "T3", "T4"]
DROP = {"researcher"}


def score_run(path):
    """-> tier -> dict of counts, plus 'ALL'."""
    c = defaultdict(lambda: defaultdict(int))
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("source_type") in DROP:
            continue
        v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
        c[r["tier"]][v] += 1
        c["ALL"][v] += 1
    return c


def metrics(d):
    n = sum(d.values())
    if not n:
        return None
    corr, wrong, na = d["CORRECT"], d["WRONG"], d["NO_ANSWER"]
    ans = n - na
    return {"n": n, "correct": corr, "wrong": wrong, "refusal": d["REFUSAL"],
            "ambiguous": d["AMBIGUOUS"], "no_answer": na,
            "raw": 100.0 * corr / n,
            "answered": 100.0 * corr / ans if ans else float("nan"),
            "penalized": (corr + HALLUCINATION_PENALTY * wrong) / n,
            "refusal_pct": 100.0 * d["REFUSAL"] / n}


def collect(pattern):
    runs = sorted(glob.glob(pattern))
    if not runs:
        sys.exit(f"no runs matched {pattern}")
    return runs, [score_run(p) for p in runs]


def agg(scored, tier, key):
    vals = [metrics(s[tier])[key] for s in scored if s.get(tier)]
    return vals


def fmt(vals, pct=True):
    m, lo, hi = st.mean(vals), min(vals), max(vals)
    u = "%" if pct else ""
    return f"{m:6.2f}{u} [{lo:.2f}-{hi:.2f}]", m, hi - lo


base_runs, base = collect("/home/mark/ikp_glm/ikp_glm_base*.jsonl")
reap_runs, reap = collect("/home/mark/ikp_glm/ikp_glm_reap_rep*.jsonl")
print(f"base K={len(base)}  {[p.rsplit('/',1)[-1] for p in base_runs]}")
print(f"reap K={len(reap)}  {[p.rsplit('/',1)[-1] for p in reap_runs]}")
n_b = metrics(base[0]["ALL"])["n"]; n_r = metrics(reap[0]["ALL"])["n"]
print(f"probes scored per run: base={n_b}  reap={n_r}"
      + ("   *** MISMATCH — not comparable ***" if n_b != n_r else ""))

print("\n=== G-5: no_answer (must be comparable, <=2pp spread) ===")
for name, S in (("base", base), ("reap", reap)):
    v = [100.0 * metrics(s["ALL"])["no_answer"] / metrics(s["ALL"])["n"] for s in S]
    print(f"  {name}: mean {st.mean(v):.2f}%  range [{min(v):.2f}-{max(v):.2f}]")
nb = st.mean([100.0 * metrics(s["ALL"])["no_answer"] / metrics(s["ALL"])["n"] for s in base])
nr = st.mean([100.0 * metrics(s["ALL"])["no_answer"] / metrics(s["ALL"])["n"] for s in reap])
print(f"  spread = {abs(nr-nb):.2f}pp  ->  " +
      ("OK" if abs(nr - nb) <= 2.0 else "*** EXCEEDS 2pp: knowledge delta NOT interpretable ***"))

for key, label, pct in (("raw", "RAW ACCURACY", True),
                        ("penalized", "PENALIZED (hallucination-weighted)", False),
                        ("refusal_pct", "REFUSAL RATE", True)):
    print(f"\n=== {label} — mean [min-max] across K=5 ===")
    print(f"  {'tier':<6}{'base':>22}{'reap':>22}{'delta':>10}{'noise':>9}{'margin':>9}")
    for t in TIERS + ["ALL"]:
        b = agg(base, t, key); r = agg(reap, t, key)
        if not b or not r:
            continue
        sb, mb, rb = fmt(b, pct); sr, mr, rr = fmt(r, pct)
        d = mr - mb
        noise = max(rb, rr)                       # worst within-arm range = the floor to beat
        margin = abs(d) / noise if noise > 1e-9 else float("inf")
        flag = ""
        if key != "refusal_pct":
            flag = "  <-- exceeds noise" if abs(d) > noise else "  (within noise)"
        print(f"  {t:<6}{sb:>22}{sr:>22}{d:>+10.2f}{noise:>9.2f}{margin:>8.1f}x{flag}")

print("\n=== Pre-registered predictions ===")
b1 = st.mean(agg(base, "T1", "raw")); r1 = st.mean(agg(reap, "T1", "raw"))
print(f"  P-R1  T1 within +/-2pp        : base {b1:.2f} -> reap {r1:.2f}, delta {r1-b1:+.2f}pp"
      f"  -> {'HELD' if abs(r1-b1) <= 2.0 else 'FALSIFIED'}")
b34 = [(metrics(s["T3"])["correct"] + metrics(s["T4"])["correct"]) * 100.0 /
       (metrics(s["T3"])["n"] + metrics(s["T4"])["n"]) for s in base]
r34 = [(metrics(s["T3"])["correct"] + metrics(s["T4"])["correct"]) * 100.0 /
       (metrics(s["T3"])["n"] + metrics(s["T4"])["n"]) for s in reap]
d34 = st.mean(r34) - st.mean(b34)
print(f"  P-R2  T3+T4 drops >=5pp       : base {st.mean(b34):.2f} -> reap {st.mean(r34):.2f}, "
      f"delta {d34:+.2f}pp  -> {'HELD' if d34 <= -5.0 else 'FALSIFIED'}")
print("  P-R3  HumanEval+ within 2pp   : NOT RUN (reasoning arm pending)")
