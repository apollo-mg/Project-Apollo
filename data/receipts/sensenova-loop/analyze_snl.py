#!/usr/bin/env python3
"""Registered analysis for PREREG_SENSENOVA_LOOP.md. Arms in quant-abstention/raw/main_<ARM>.jsonl: SNL, Q35R, SNLH
(exploratory) and the stored Q35B (replay comparison only). Grading: the run_main grader with the bare-answer rule
(idk-lora/bare_rule.py). Paired bootstrap over items, 10,000 resamples, seed 20261123.
Usage: analyze_snl.py [--out RESULT_snl.json]"""
import argparse, json, statistics, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
SEED, NB = 20261123, 10000
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")


def load(arm, items):
    p = QA / "raw" / f"main_{arm}.jsonl"
    if not p.exists(): return None
    rows = {r["id"]: r for r in map(json.loads, open(p)) if "id" in r}
    for i, r in rows.items():
        if i in items and "content" in r: r["grade"] = regrade(items[i], r)
    return rows if all(i in rows for i in items) else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_snl.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in ("E", "H", "U")}
    R = {arm: load(arm, items) for arm in ("SNL", "Q35R", "SNLH", "Q35B")}
    out = {"arms": {}, "tests": {}}
    print(f"{'arm':6s} {'invented declined':>17s} {'hard right/wrong/declined':>26s} {'easy right':>10s} {'unfinished':>10s} {'median out tok':>14s} {'median tok/s':>12s}")
    for arm, rows in R.items():
        if rows is None: print(f"{arm:6s} (missing or incomplete)"); continue
        g = {i: rows[i]["grade"] for i in items}
        wrong = lambda k: sum(1 for i in by[k] if g[i] not in ("CORRECT", "ABSTAINED") and g[i] not in UNF)
        toks = [((rows[i].get("gen_usage") or {}).get("completion_tokens")) for i in items]
        tps = [rows[i].get("gen_tps") for i in items]
        o = {"invented_declined": sum(g[i] == "ABSTAINED" for i in by["U"]),
             "hard_right": sum(g[i] == "CORRECT" for i in by["H"]), "hard_wrong": wrong("H"),
             "hard_declined": sum(g[i] == "ABSTAINED" for i in by["H"]),
             "easy_right": sum(g[i] == "CORRECT" for i in by["E"]), "unfinished": sum(g[i] in UNF for i in items),
             "median_out_tokens": statistics.median([t for t in toks if t is not None]) if any(t is not None for t in toks) else None,
             "median_tps": statistics.median([t for t in tps if t]) if any(tps) else None}
        out["arms"][arm] = o
        tps_s = f"{o['median_tps']:.1f}" if o["median_tps"] else "-"
        print(f"{arm:6s} {o['invented_declined']:>13d}/100 {o['hard_right']:>14d}/{o['hard_wrong']}/{o['hard_declined']:<8d} "
              f"{o['easy_right']:>7d}/40 {o['unfinished']:>10d} {str(o['median_out_tokens']):>14s} {tps_s:>12s}")
    rng = np.random.default_rng(SEED)
    def paired(x, y, ids, f):
        d = np.array([f(x[i]) - f(y[i]) for i in ids], float)
        bs = d[rng.integers(0, len(d), (NB, len(d)))].mean(1)
        return float(d.mean()), (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
    S, Q = R["SNL"], R["Q35R"]
    if S and Q:
        dec = lambda r: float(r["grade"] == "ABSTAINED"); acc = lambda r: float(r["grade"] == "CORRECT")
        m1, c1 = paired(S, Q, by["U"], dec); m2, c2 = paired(S, Q, by["H"], acc)
        out["tests"]["H1"] = {"diff": m1, "ci95": c1, "holds": m1 < 0}
        out["tests"]["H2"] = {"diff": m2, "ci95": c2, "holds": m2 <= 0.05}
        print(f"\n- H1 invented declined, SNL - Q35R: {m1:+.2f} [{c1[0]:+.2f}, {c1[1]:+.2f}] -> {'holds' if m1 < 0 else 'FAILS'} (fewer declined predicted)")
        print(f"- H2 hard accuracy, SNL - Q35R: {m2:+.2f} [{c2[0]:+.2f}, {c2[1]:+.2f}] -> {'holds' if m2 <= 0.05 else 'FAILS'} (at most +0.05 predicted)")
        m3, c3 = paired(S, Q, by["E"], acc)
        print(f"- easy accuracy, SNL - Q35R: {m3:+.3f} [{c3[0]:+.3f}, {c3[1]:+.3f}] (no prediction)")
    if S and R["SNLH"]:
        H = R["SNLH"]; diff = sum(S[i].get("content") != H[i].get("content") for i in items)
        gd = sum(S[i]["grade"] != H[i]["grade"] for i in items)
        out["tests"]["E1"] = {"answers_differ": diff, "grades_differ": gd, "holds": diff >= 24}
        print(f"- E1 head build (shared caches) vs SNL: {diff} of 240 answers differ, {gd} grades differ -> "
              f"{'holds' if diff >= 24 else 'FAILS'} (>= 24 predicted)")
    if Q and R["Q35B"]:
        B = R["Q35B"]
        print(f"- replay (not a gate): Q35R vs stored Q35B: {sum(Q[i].get('content') == B[i].get('content') for i in items)} of 240 "
              f"answers identical, {sum(Q[i]['grade'] == B[i]['grade'] for i in items)} grades identical")
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
