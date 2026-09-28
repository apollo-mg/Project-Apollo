#!/usr/bin/env python3
"""Registered analysis for PREREG_FLASHNEXT_MTP_CLOCK.md (committed before any row). Per (mtp, cfg): median decode
tok/s over 6 prompts x 2 blocks, acceptance (sum accepted / sum drafted), median prefill tok/s, and tok/J from the
power log (sum of the 4 GPUs' power.draw sampled inside each decode request's window x its duration).
Usage: analyze_mtp_clock.py [DIR]"""
import csv, json, statistics as st, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
D = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "mtp_clock"
rows = [json.loads(l) for l in open(D / "rows.jsonl")]
P = defaultdict(float); N = defaultdict(int)                      # timestamp (0.2 s bucket) -> summed watts over GPUs
for rec in csv.reader(open(D / "power.csv")):
    try:
        ts = datetime.strptime(rec[0].strip(), "%Y/%m/%d %H:%M:%S.%f").timestamp()
        k = round(ts * 5); P[k] += float(rec[2]); N[k] += 1
    except (ValueError, IndexError):
        pass
full = {k: w for k, w in P.items() if N[k] == 4}                   # only samples where all 4 GPUs reported
def joules(r):
    ks = [k for k in range(int(r["t0"] * 5), int(r["t1"] * 5) + 1) if k in full]
    return (st.mean(full[k] for k in ks) * (r["t1"] - r["t0"])) if ks else None
S = {}
for mtp in ("off", "on"):
    for c in ("E", "P", "B"):
        dec = [r for r in rows if r["mtp"] == mtp and r["cfg"] == c and r["prompt"] != "prefill"]
        pre = [r for r in rows if r["mtp"] == mtp and r["cfg"] == c and r["prompt"] == "prefill"]
        if not dec:
            continue
        J = [(r["predicted_n"], joules(r)) for r in dec]
        J = [(n, j) for n, j in J if j]
        s = {"dec": st.median(r["predicted_per_second"] for r in dec), "n": len(dec),
             "acc": (sum(r["draft_n_accepted"] or 0 for r in dec) / max(1, sum(r["draft_n"] or 0 for r in dec))) if mtp == "on" else None,
             "pre": st.median(r["prompt_per_second"] for r in pre) if pre else None,
             "tokJ": (sum(n for n, _ in J) / sum(j for _, j in J)) if J else None,
             "W": (sum(j for _, j in J) / sum(r["t1"] - r["t0"] for r in dec if joules(r))) if J else None}
        S[(mtp, c)] = s
        print(f"MTP {mtp:3s} {c}: decode {s['dec']:6.2f} tok/s (n={s['n']})  prefill {s['pre'] or 0:7.1f}  "
              f"tok/J {s['tokJ'] or 0:.4f}  mean W {s['W'] or 0:6.1f}" + (f"  acceptance {s['acc']:.3f}" if s['acc'] is not None else ""))
g = lambda m, c, k: S[(m, c)][k]
res = {}
try:
    res["M1"] = g("on", "E", "dec") / g("off", "E", "dec") >= 1.4
    r_on, r_off = g("on", "P", "dec") / g("on", "E", "dec"), g("off", "P", "dec") / g("off", "E", "dec")
    print(f"clock gain P/E: MTP on {r_on:.3f}, off {r_off:.3f}; MTP speedup at E {g('on', 'E', 'dec') / g('off', 'E', 'dec'):.3f}")
    res["M2"] = r_on - r_off >= 0.05
    res["M3"] = all(abs(g(m, "B", "dec") / g(m, "P", "dec") - 1) <= 0.03 for m in ("off", "on"))
    adv_off, adv_on = g("off", "E", "tokJ") / g("off", "P", "tokJ") - 1, g("on", "E", "tokJ") / g("on", "P", "tokJ") - 1
    print(f"pin's tok/J advantage (E over P): MTP off {adv_off:+.3f}, on {adv_on:+.3f}")
    res["M4"] = adv_off >= 0 and adv_on < adv_off
except (KeyError, TypeError, ZeroDivisionError) as e:
    print("predictions incomplete:", e)
for k, v in res.items():
    print(k, "HOLDS" if v else "does not hold")
