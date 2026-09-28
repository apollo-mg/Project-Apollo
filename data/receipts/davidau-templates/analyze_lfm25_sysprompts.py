#!/usr/bin/env python3
"""Registered analysis for PREREG_LFM25_SYSPROMPTS.md (committed before any row). Per arm: answerable CORRECT /24,
unanswerable ABSTAINED /24, median tokens. Q0-Q3 as registered. Q3 compares OMNI with the stored TRIM/omni rows of
lfm25_modes/rows.jsonl (byte-identical renders, same seeds)."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
from scipy.stats import fisher_exact
H = Path(__file__).resolve().parent
rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else H / "lfm25_sysprompts" / "rows.jsonl")]
C = defaultdict(list)
for r in rows: C[r["arm_sys"]].append(r)
S = {}
for arm in ("NONE", "XHIGH", "OMNI", "OMNID2"):
    rs = C[arm]; A = [r for r in rs if r["arm"] == "answerable"]; U = [r for r in rs if r["arm"] == "unanswerable"]
    S[arm] = {"A": sum(r["grade"] == "ANSWERED-CORRECT" for r in A), "nA": len(A), "U": sum(r["grade"] == "ABSTAINED" for r in U),
              "nU": len(U), "tok": st.median([r["completion_tokens"] for r in rs if "completion_tokens" in r] or [0]),
              "nostop": sum(r["grade"] == "NO-STOP" for r in rs)}
    s = S[arm]; print(f"{arm:7s} answerable {s['A']}/{s['nA']}  unanswerable refused {s['U']}/{s['nU']}  median tok {s['tok']:.0f}  NO-STOP {s['nostop']}")
fx = lambda a, b, alt, key: fisher_exact([[S[a][key], S[a]["n" + key] - S[a][key]], [S[b][key], S[b]["n" + key] - S[b][key]]], alternative=alt)[1]
res = {}
q0 = {a: fx(a, "NONE", "less", "U") for a in ("XHIGH", "OMNI", "OMNID2")}
print("Q0 one-sided p (arm refuses less than NONE):", {k: round(v, 4) for k, v in q0.items()}); res["Q0"] = all(v < 0.05 / 3 for v in q0.values())
pu, pa = fx("XHIGH", "OMNI", "two-sided", "U"), fx("XHIGH", "OMNI", "two-sided", "A")
print(f"Q1 XHIGH vs OMNI two-sided p: refused {pu:.3f}, answerable {pa:.3f}; tokens {S['XHIGH']['tok']:.0f} vs {S['OMNI']['tok']:.0f}")
res["Q1"] = pu >= 0.05 and pa >= 0.05 and S["XHIGH"]["tok"] <= 0.5 * S["OMNI"]["tok"]
q2 = fx("OMNID2", "OMNI", "less", "U"); print(f"Q2 OMNID2 refuses less than OMNI: one-sided p {q2:.3f}"); res["Q2"] = q2 < 0.05
old = {(r["seed"], r["id"]): r for r in map(json.loads, open(H / "lfm25_modes" / "rows.jsonl")) if r["template"] == "TRIM" and r["mode"] == "omni"}
same = sum(1 for r in C["OMNI"] if (r["seed"], r["id"]) in old and old[(r["seed"], r["id"])]["grade"] == r["grade"]
           and old[(r["seed"], r["id"])].get("completion_tokens") == r.get("completion_tokens"))
print(f"Q3 OMNI vs stored TRIM/omni: same grade and token count on {same}/{len(C['OMNI'])}"); res["Q3"] = same >= 46
for k, v in res.items(): print(k, "HOLDS" if v else "does not hold")
