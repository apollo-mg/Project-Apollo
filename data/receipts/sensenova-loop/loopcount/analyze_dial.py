#!/usr/bin/env python3
"""Registered analysis for PREREG_LOOP_DIAL.md: SNL (2 loops, 11-23), SNL_L1, SNL_L3; bare-answer rule; paired bootstrap
against 2 loops over items, 10,000, seed 20261125. Usage: analyze_dial.py [--out RESULT_dial.json]"""
import argparse, json, statistics, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; QA = HERE.parent.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")
def load(arm, items):
    rows = {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
    for i, r in rows.items():
        if "content" in r: r["grade"] = regrade(items[i], r)
    return rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_dial.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in "EHU"}
    R = {1: load("SNL_L1", items), 2: load("SNL", items), 3: load("SNL_L3", items)}; out = {"arms": {}, "vs2": {}}
    for n, r in R.items():
        g = {i: r[i]["grade"] for i in items}
        toks = [((r[i].get("gen_usage") or {}).get("completion_tokens")) for i in items]
        o = {"invented_declined": sum(g[i] == "ABSTAINED" for i in by["U"]), "invented_answered": sum(g[i] not in UNF and g[i] != "ABSTAINED" for i in by["U"]),
             "hard_right": sum(g[i] == "CORRECT" for i in by["H"]), "hard_wrong": sum(g[i] not in ("CORRECT", "ABSTAINED") and g[i] not in UNF for i in by["H"]),
             "hard_declined": sum(g[i] == "ABSTAINED" for i in by["H"]), "easy_right": sum(g[i] == "CORRECT" for i in by["E"]),
             "unfinished": sum(g[i] in UNF for i in items), "median_tokens": statistics.median([t for t in toks if t is not None]),
             "median_tps": round(statistics.median([r[i]["gen_tps"] for i in items if r[i].get("gen_tps")]), 1)}
        out["arms"][n] = o; print(f"{n} loop(s):", o)
    rng = np.random.default_rng(20261125)
    def paired(n, ids, f):
        d = np.array([f(R[n][i]) - f(R[2][i]) for i in ids], float); bs = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
        return round(float(d.mean()), 3), (round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3))
    for n in (1, 3):
        out["vs2"][n] = {"invented_declined": paired(n, by["U"], lambda r: float(r["grade"] == "ABSTAINED")),
                         "hard_right": paired(n, by["H"], lambda r: float(r["grade"] == "CORRECT")),
                         "easy_right": paired(n, by["E"], lambda r: float(r["grade"] == "CORRECT"))}
        print(f"{n} loops minus 2 loops:", out["vs2"][n])
    h1, h2, h3 = out["arms"][1]["hard_right"], out["arms"][2]["hard_right"], out["arms"][3]["hard_right"]
    out["D1"] = h1 <= h2; out["D2"] = h3 <= h2 + 3
    print(f"D1 hard right at 1 loop at most 2-loop's ({h1} vs {h2}): {'holds' if out['D1'] else 'FAILS'}")
    print(f"D2 hard right at 3 loops at most {h2}+3 ({h3}): {'holds' if out['D2'] else 'FAILS'}")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
