#!/usr/bin/env python3
"""Score the fixed-byte allocation arms against PREREG_FIXED_BYTE.md (57a82de).

Bytes are held constant (~13.2 GB, 2.4% spread); prune ratio and bit depth move together
BY DESIGN, so "monotone in prune ratio" and "monotone in bits" are the same axis read
backwards. Both orderings are printed so nobody reads one as independent evidence for the other.

FB-REAP50 is NOT re-run: the dose-response leg measured that exact file under these exact
settings. Its jsonl is passed in from that leg and labelled REUSED wherever it appears.

Usage: fb_analyze.py FBBASE.jsonl FBREAP09.jsonl FBREAP19.jsonl FBREAP39.jsonl REUSED_REAP50.jsonl
"""
import json, sys
sys.path.insert(0, "/mnt/TG_2TB/Projects/Apollo/data/receipts/ikp")
from ikp_score import grade

# label, experts, %pruned, quant, GB, reused?
ARMS = [("FBBASE",   64,  0.0, "Q3_K_S", 13.03, False),
        ("FBREAP09", 58,  9.4, "Q3_K_M", 13.14, False),
        ("FBREAP19", 52, 18.8, "Q3_K_L", 12.90, False),
        ("FBREAP39", 39, 39.1, "Q5_K_S", 13.19, False),
        ("FBREAP50", 32, 50.0, "Q6_K",   13.21, True)]

# Reference points from RESULT_REAP_DOSE_RESPONSE.md — all Q6_K, NOT byte-matched.
REF_BASE_Q6K_RAW   = 0.689   # 24.61 GB
REF_REAP09_Q6K_RAW = 0.525   # 22.48 GB
REF_REAP09_Q6K_GB  = 22.48


def load(p):
    rs = [json.loads(l) for l in open(p) if l.strip()]
    v = [grade(r["gold"], r.get("response", ""), 25, r.get("finish_reason"))[0] for r in rs]
    c, w = v.count("CORRECT"), v.count("WRONG")
    return dict(n=len(v), c=c, w=w, rf=v.count("REFUSAL"), am=v.count("AMBIGUOUS"),
                na=v.count("NO_ANSWER"), raw=c / len(v),
                cm=(c / (c + w) if (c + w) else float("nan")), cn=c + w)


D = {}
for (lab, *_), path in zip(ARMS, sys.argv[1:6]):
    D[lab] = load(path)

hdr = (f"{'arm':<10}{'exp':>4}{'%pr':>6}{'quant':>9}{'GB':>7}"
       f"{'RAW acc':>9}{'refus':>8}{'committed':>11}{'(n)':>7}{'noans':>7}")
print(hdr); print("-" * len(hdr))
for lab, ex, pr, q, gb, reused in ARMS:
    d = D[lab]
    tag = "  <- REUSED from dose-response leg" if reused else ""
    print(f"{lab:<10}{ex:>4}{pr:>6.1f}{q:>9}{gb:>7.2f}{d['raw']:>8.1%}{d['rf']/d['n']:>8.1%}"
          f"{d['cm']:>10.1%}{d['cn']:>7}{d['na']/d['n']:>7.1%}{tag}")
print("-" * len(hdr))

nas = [D[l]["na"] / D[l]["n"] for l, *_ in ARMS]
print(f"\n=== G-5  no_answer spread {max(nas)-min(nas):.1%} -> "
      f"{'OK' if max(nas)-min(nas) <= 0.02 else 'TRIPPED'}")
thin = [l for l, *_ in ARMS if D[l]["cn"] < 100]
if thin:
    print(f"=== committed n < 100 on {', '.join(thin)} — committed accuracy INDICATIVE ONLY there;"
          f"\n    raw accuracy is the headline (rule from RESULT_REAP_DOSE_RESPONSE.md)")

print("\n=== PREDICTION SCORING (PREREG_FIXED_BYTE.md §8) ===")
b = D["FBBASE"]["raw"]
print(f"  P-F0  GATE FBBASE raw >= 30%            : {b:.1%} -> {'HELD' if b >= 0.30 else 'FAILED'}")

gap = b - D["FBREAP50"]["raw"]
print(f"  P-F1  HINGE FBBASE beats FBREAP50 >=30pp: {b:.1%} vs {D['FBREAP50']['raw']:.1%}, "
      f"gap {gap*100:+.1f}pp -> {'HELD' if gap >= 0.30 else 'FALSIFIED'}")

seq = [D[l]["raw"] for l, *_ in ARMS]
viol = [(ARMS[i][0], ARMS[i+1][0], seq[i], seq[i+1])
        for i in range(len(seq)-1) if seq[i+1] > seq[i] + 0.03]
print(f"  P-F2  raw monotone DEC in prune ratio   : {' -> '.join(f'{x:.1%}' for x in seq)}")
print(f"        {'HELD' if not viol else 'FALSIFIED at ' + ', '.join(f'{a}->{c}' for a,c,_,_ in viol)}")
if viol:
    peak = max(ARMS, key=lambda a: D[a[0]]["raw"])
    print(f"        PEAK at {peak[0]} ({peak[2]:.1f}% pruned, {peak[3]}) — a sweet spot exists; "
          f"this is the pro-REAP outcome named in the prereg")

rfs = [D[l]["rf"] / D[l]["n"] for l, *_ in ARMS]
mono_rf = all(rfs[i+1] >= rfs[i] - 0.01 for i in range(len(rfs)-1))
print(f"  P-F3  refusal monotone INC              : {' -> '.join(f'{x:.1%}' for x in rfs)}"
      f" -> {'HELD' if mono_rf else 'FALSIFIED'}")

dom = b > REF_REAP09_Q6K_RAW
print(f"  P-F4  DOMINANCE FBBASE(13.03GB) beats REAP-09 Q6_K(22.48GB, raw 52.5%)")
print(f"        {b:.1%} vs {REF_REAP09_Q6K_RAW:.1%} -> {'HELD' if dom else 'FALSIFIED'}"
      + (f"   ** REAP dominated on BOTH axes: worse accuracy AND 42% larger **" if dom else ""))

print("\n=== THE ALLOCATION QUESTION: ~13.2 GB, how to spend it ===")
print("  (prune ratio and bit depth are the SAME axis here — read as one trade, not two)")
for lab, ex, pr, q, gb, reused in ARMS:
    d = D[lab]
    bar = "#" * int(round(d["raw"] * 60))
    print(f"  {ex:>2} experts @ {q:<7} {gb:>5.2f}GB  raw {d['raw']:>6.1%}  {bar}")
print(f"\n  reference, NOT byte-matched:")
print(f"  64 experts @ Q6_K    24.61GB  raw {REF_BASE_Q6K_RAW:>6.1%}")
print(f"  58 experts @ Q6_K    {REF_REAP09_Q6K_GB:>5.2f}GB  raw {REF_REAP09_Q6K_RAW:>6.1%}")

spread = max(seq) - min(seq)
if spread < 0.10:
    print(f"\n  !! raw-accuracy spread across all arms is only {spread*100:.1f}pp — at this budget the"
          f"\n     BYTES are the binding constraint, not the allocation. P-F2 should be read as"
          f"\n     unscoreable in spirit even if it technically passes.")
