#!/usr/bin/env python3
"""Score the REAP dose-response ladder against PREREG_REAP_DOSE_RESPONSE.md (6184f08).

Metric is committed accuracy = correct/(correct+wrong), excluding refusals and NO_ANSWER,
identical to every prior leg. Usage:
    ladder_analyze.py ikp_BASE.jsonl ikp_REAP09.jsonl ikp_REAP19.jsonl ikp_REAP39.jsonl ikp_REAP50.jsonl
"""
import json, sys
from collections import defaultdict
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

ARMS = [("BASE", 64, 0.0), ("REAP09", 58, 9.4), ("REAP19", 52, 18.8),
        ("REAP39", 39, 39.1), ("REAP50", 32, 50.0)]
TIERS = ("T1", "T2", "T3", "T4")


TOK = {}


def load(p):
    out = defaultdict(list)
    toks = []
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        r = json.loads(l)
        v, _ = grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))
        out[r["tier"]].append(v)
        out["ALL"].append(v)
        ct = r.get("completion_tokens")
        if isinstance(ct, int):
            toks.append(ct)
    out["_toks"] = toks
    return out


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float("nan")
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


A = {}
for (lab, _, _), path in zip(ARMS, sys.argv[1:6]):
    A[lab] = load(path)

def cell(lab, t):
    vs = A[lab].get(t, [])
    c = vs.count("CORRECT"); w = vs.count("WRONG")
    rf = vs.count("REFUSAL"); am = vs.count("AMBIGUOUS"); na = vs.count("NO_ANSWER")
    return dict(n=len(vs), c=c, w=w, rf=rf, am=am, na=na,
                cm=(c / (c + w) if (c + w) else float("nan")), raw=(c / len(vs) if vs else 0))

hdr = f"{'arm':<8}{'exp':>4}{'%pr':>6}" + "".join(f"{t:>9}" for t in TIERS) + f"{'ALL':>9}{'refus':>8}{'noans':>7}"
print(hdr); print("-" * len(hdr))
CM = {}
for lab, ex, pr in ARMS:
    row = f"{lab:<8}{ex:>4}{pr:>6.1f}"
    for t in TIERS:
        d = cell(lab, t); CM[(lab, t)] = d["cm"]
        row += f"{d['cm']:>8.1%}"
    d = cell(lab, "ALL"); CM[(lab, "ALL")] = d["cm"]
    row += f"{d['cm']:>8.1%}{d['rf']/d['n']:>8.1%}{d['na']/d['n']:>7.1%}"
    print(row)
print("-" * len(hdr))
print("(committed accuracy = correct/(correct+wrong); refusals and NO_ANSWER excluded)\n")

# ---- G-5: truncation spread across arms voids an accuracy delta ----
nas = [cell(lab, "ALL")["na"] / cell(lab, "ALL")["n"] for lab, _, _ in ARMS]
print(f"=== G-5  no_answer across arms: {' '.join(f'{x:.1%}' for x in nas)}"
      f"   spread {max(nas)-min(nas):.1%}"
      f"  -> {'OK' if max(nas)-min(nas) <= 0.02 else 'TRIPPED — bound before claiming any delta'}\n")

print("=== PREDICTION SCORING (PREREG_REAP_DOSE_RESPONSE.md §8) ===")
b1 = CM[("BASE", "T1")]
qx0 = b1 >= 0.85
print(f"  P-L0  GATE base committed T1 >= 85%      : {b1:.1%} -> {'HELD' if qx0 else 'FAILED'}")

seq = [CM[(lab, "T1")] for lab, _, _ in ARMS]
viol = [(ARMS[i][0], ARMS[i+1][0], seq[i], seq[i+1])
        for i in range(len(seq)-1) if seq[i+1] > seq[i] + 0.03]
print(f"  P-L1  T1 non-increasing (3pp slack)      : "
      f"{' -> '.join(f'{x:.1%}' for x in seq)}")
print(f"        {'HELD' if not viol else 'FALSIFIED at ' + ', '.join(f'{a}->{b} ({x:.1%}->{y:.1%})' for a,b,x,y in viol)}")

d09 = b1 - CM[("REAP09", "T1")]
print(f"  P-L2  HINGE REAP-09 loses < 10pp on T1   : {d09*100:+.1f}pp -> "
      f"{'HELD' if d09 < 0.10 else 'FALSIFIED'}")

d50 = b1 - CM[("REAP50", "T1")]
print(f"  P-L3  REAP-50 loses > 40pp on T1         : {d50*100:+.1f}pp -> "
      f"{'HELD' if d50 > 0.40 else 'FALSIFIED'}")

late = CM[("REAP39", "T1")] - CM[("REAP50", "T1")]
early = d09
if early <= 0:
    verdict = f"early loss is {early*100:+.1f}pp (<=0) — ratio undefined; convexity read from the curve"
else:
    verdict = f"late/early = {late/early:.2f}x -> {'HELD' if late >= 3*early else 'FALSIFIED'}"
print(f"  P-L4  convex: 39->50 loss >= 3x 0->09    : late {late*100:+.1f}pp, early {early*100:+.1f}pp; {verdict}")

rfs = [cell(lab, "ALL")["rf"] / cell(lab, "ALL")["n"] for lab, _, _ in ARMS]
mono = all(rfs[i+1] >= rfs[i] - 0.01 for i in range(len(rfs)-1))
print(f"  P-L5  refusal rises monotonically        : {' -> '.join(f'{x:.1%}' for x in rfs)}"
      f" -> {'HELD' if mono else 'FALSIFIED'}")

def tail_loss(lab):
    b34 = [CM[("BASE", t)] for t in ("T3", "T4")]
    a34 = [CM[(lab, t)] for t in ("T3", "T4")]
    return sum(b34) / 2 - sum(a34) / 2

t09, h09 = tail_loss("REAP09"), d09
sel = (t09 >= 2 * h09) if h09 > 0 else (t09 > 0.05)
broad = d50 >= 0.25
print(f"  P-L6  tail-selectivity is a dose effect  : REAP-09 T3+T4 loss {t09*100:+.1f}pp vs "
      f"T1 loss {h09*100:+.1f}pp ({'selective' if sel else 'not selective'}); "
      f"REAP-50 T1 loss {d50*100:+.1f}pp ({'broad' if broad else 'not broad'})")
print(f"        -> {'HELD' if (sel and broad) else 'FALSIFIED'}")

# ---- NOT PRE-REGISTERED: generation length by arm ----
# The pruned arms ran 4-5x slower than base in wall-clock on identical probes and identical
# hardware. Smaller models should be FASTER, so the suspect is tokens generated per probe.
# Reported as an observation, never as a scored prediction.
print("\n=== VERBOSITY BY ARM (post-hoc observation, NOT pre-registered) ===")
print(f"{'arm':<8}{'exp':>4}{'mean tok':>10}{'median':>9}{'max':>7}{'vs base':>10}")
base_mean = None
for lab, ex, _ in ARMS:
    t = A[lab].get("_toks", [])
    if not t:
        print(f"{lab:<8}{ex:>4}{'(no completion_tokens recorded)':>36}")
        continue
    m = sum(t) / len(t)
    if base_mean is None:
        base_mean = m
    print(f"{lab:<8}{ex:>4}{m:>10.1f}{med(t):>9.0f}{max(t):>7}"
          f"{(m/base_mean if base_mean else 1):>9.2f}x")
print("  (a rising ratio = the pruned arm generates more before terminating, i.e. a stopping\n"
      "   failure rather than an answering failure — the same shape as the Puzzle/Laguna gap)")

print("\n=== THE CURVE (committed T1, and ALL) ===")
for lab, ex, pr in ARMS:
    bar = "#" * int(round(CM[(lab, "ALL")] * 50))
    print(f"  {pr:>5.1f}% pruned ({ex:>2} exp)  T1 {CM[(lab,'T1')]:>6.1%}  ALL {CM[(lab,'ALL')]:>6.1%}  {bar}")
