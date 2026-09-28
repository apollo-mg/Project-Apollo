#!/usr/bin/env python3
"""Registered analysis for PREREG_LFM25_MODES.md (committed before any row existed).
Per (template, mode): answerable CORRECT of 24, unanswerable ABSTAINED of 24, NO-STOP, ERROR, parse-suspect rows
(n_matches > 1), median completion tokens. Predictions P1-P4 exactly as registered.
Usage: analyze_lfm25_modes.py [rows.jsonl]"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
rows = [json.loads(l) for l in open(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "lfm25_modes" / "rows.jsonl")]
C = defaultdict(list)
for r in rows:
    C[(r["template"], r["mode"])].append(r)
S = {}
print(f"{'template/mode':16s} {'n':>3s} {'A-correct':>9s} {'U-abstain':>9s} {'NO-STOP':>7s} {'ERR':>3s} {'suspect':>7s} {'med tok':>7s}")
for (t, m), rs in sorted(C.items(), key=lambda kv: (kv[0][0], ["off", "low", "high", "ultra", "einstein", "spoon", "omni"].index(kv[0][1]))):
    A = [r for r in rs if r["arm"] == "answerable"]; U = [r for r in rs if r["arm"] == "unanswerable"]
    s = {"n": len(rs), "A_correct": sum(r["grade"] == "ANSWERED-CORRECT" for r in A), "nA": len(A),
         "U_abstain": sum(r["grade"] == "ABSTAINED" for r in U), "nU": len(U),
         "nostop": sum(r["grade"] == "NO-STOP" for r in rs), "err": sum(r["grade"] == "ERROR" for r in rs),
         "suspect": sum((r.get("n_matches") or 0) > 1 for r in rs),
         "med_tok": st.median([r["completion_tokens"] for r in rs if "completion_tokens" in r] or [0])}
    S[(t, m)] = s
    print(f"{t + '/' + m:16s} {s['n']:3d} {s['A_correct']:5d}/{s['nA']:<3d} {s['U_abstain']:5d}/{s['nU']:<3d} {s['nostop']:7d} {s['err']:3d} {s['suspect']:7d} {s['med_tok']:7.0f}")
g = lambda t, m, k: S.get((t, m), {}).get(k)
res = {}
from scipy.stats import fisher_exact, mannwhitneyu
def tok(t, m):
    return [r["completion_tokens"] for r in C[(t, m)] if "completion_tokens" in r]
def fx(k1, n1, k2, n2, alt):
    return fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative=alt)[1]
try:
    res["P1"] = (g("ORIG", "omni", "med_tok") >= 3 * g("ORIG", "high", "med_tok") and g("ORIG", "spoon", "med_tok") >= 3 * g("ORIG", "high", "med_tok")
                 and g("ORIG", "low", "med_tok") <= g("ORIG", "high", "med_tok"))
    # P2: no mode is significantly MORE accurate than off on answerable items (one-sided Fisher, uncorrected p < 0.05 = a gain)
    p2 = {m: fx(g("ORIG", m, "A_correct"), g("ORIG", m, "nA"), g("ORIG", "off", "A_correct"), g("ORIG", "off", "nA"), "greater")
          for m in ["low", "high", "ultra", "einstein", "spoon", "omni"]}
    print("P2 one-sided p (mode > off, answerable):", {m: round(v, 3) for m, v in p2.items()})
    res["P2"] = all(v >= 0.05 / 6 for v in p2.values())         # Bonferroni over the 6 modes
    # P3: heavy modes (omni+spoon+einstein pooled) abstain LESS on unanswerable than off: one-sided p < 0.05 and >= 0.10 lower
    hk = sum(g("ORIG", m, "U_abstain") for m in ("omni", "spoon", "einstein")); hn = sum(g("ORIG", m, "nU") for m in ("omni", "spoon", "einstein"))
    ok_, on = g("ORIG", "off", "U_abstain"), g("ORIG", "off", "nU")
    p3 = fx(hk, hn, ok_, on, "less")
    print(f"P3 heavy U-abstain {hk}/{hn} vs off {ok_}/{on}, one-sided p {p3:.3f}")
    res["P3"] = p3 < 0.05 and hk / hn <= ok_ / on - 0.10
    # P4: the whitespace token is inert for off/high/omni: two-sided Fisher p >= 0.05 on both rates, Mann-Whitney p >= 0.05 on tokens
    p4 = {}
    for m in ("off", "high", "omni"):
        pa = fx(g("TRIM", m, "A_correct"), g("TRIM", m, "nA"), g("ORIG", m, "A_correct"), g("ORIG", m, "nA"), "two-sided")
        pu = fx(g("TRIM", m, "U_abstain"), g("TRIM", m, "nU"), g("ORIG", m, "U_abstain"), g("ORIG", m, "nU"), "two-sided")
        pt = mannwhitneyu(tok("TRIM", m), tok("ORIG", m), alternative="two-sided").pvalue
        p4[m] = (round(pa, 3), round(pu, 3), round(pt, 3))
    print("P4 two-sided p (A-correct, U-abstain, tokens) TRIM vs ORIG:", p4)
    res["P4"] = all(min(v) >= 0.05 / 9 for v in p4.values())    # Bonferroni over 3 modes x 3 metrics
except (TypeError, ZeroDivisionError, KeyError) as e:
    print("predictions incomplete:", e)
for k, v in res.items():
    print(k, "HOLDS" if v else "does not hold")
