#!/usr/bin/env python3
"""Registered analysis for PREREG_OLMO3_LADDER.md: OL_SFT, OL_DPO, OL_RL; bare-answer rule; paired bootstrap over items,
10,000, seed 20261125, for every pair. Usage: analyze_ladder.py [--out RESULT_ladder.json]"""
import argparse, json, statistics, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")
ARMS = ("OL_SFT", "OL_DPO", "OL_RL")
def load(arm, items):
    rows = {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
    missing = set(items) - set(rows)
    if missing: sys.exit(f"{arm}: {len(missing)} items missing")
    for i, r in rows.items():
        if "content" in r: r["grade"] = regrade(items[i], r)
    return rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_ladder.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in "EHU"}
    R = {arm: load(arm, items) for arm in ARMS}; out = {"arms": {}, "pairs": {}}
    for arm, r in R.items():
        g = {i: r[i]["grade"] for i in items}
        toks = [((r[i].get("gen_usage") or {}).get("completion_tokens")) for i in items]
        o = {"invented_declined": sum(g[i] == "ABSTAINED" for i in by["U"]),
             "invented_answered": sum(g[i] not in UNF and g[i] != "ABSTAINED" for i in by["U"]),
             "hard_right": sum(g[i] == "CORRECT" for i in by["H"]),
             "hard_wrong": sum(g[i] not in ("CORRECT", "ABSTAINED") and g[i] not in UNF for i in by["H"]),
             "hard_declined": sum(g[i] == "ABSTAINED" for i in by["H"]),
             "easy_right": sum(g[i] == "CORRECT" for i in by["E"]),
             "easy_declined": sum(g[i] == "ABSTAINED" for i in by["E"]),
             "unfinished": sum(g[i] in UNF for i in items),
             "median_tokens": statistics.median([t for t in toks if t is not None]),
             "median_tps": round(statistics.median([r[i]["gen_tps"] for i in items if r[i].get("gen_tps")]), 1)}
        out["arms"][arm] = o; print(f"{arm}:", o)
    rng = np.random.default_rng(20261125)
    def paired(x, y, ids, f):
        d = np.array([f(R[x][i]) - f(R[y][i]) for i in ids], float); bs = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
        return round(float(d.mean()), 3), (round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3))
    for x, y in (("OL_DPO", "OL_SFT"), ("OL_RL", "OL_DPO"), ("OL_RL", "OL_SFT")):
        k = f"{x}-{y}"
        out["pairs"][k] = {"invented_declined": paired(x, y, by["U"], lambda r: float(r["grade"] == "ABSTAINED")),
                           "invented_answered": paired(x, y, by["U"], lambda r: float(r["grade"] not in UNF and r["grade"] != "ABSTAINED")),
                           "hard_right": paired(x, y, by["H"], lambda r: float(r["grade"] == "CORRECT")),
                           "hard_declined": paired(x, y, by["H"], lambda r: float(r["grade"] == "ABSTAINED")),
                           "easy_right": paired(x, y, by["E"], lambda r: float(r["grade"] == "CORRECT"))}
        print(k, out["pairs"][k])
    A = out["arms"]
    p1 = abs(A["OL_RL"]["invented_declined"] - A["OL_DPO"]["invented_declined"]) / len(by["U"])
    out["P1"] = p1 <= 0.05; out["P2"] = A["OL_DPO"]["invented_declined"] < A["OL_SFT"]["invented_declined"]
    out["P3"] = abs(A["OL_RL"]["hard_right"] - A["OL_SFT"]["hard_right"]) <= 5
    print(f"P1 |RL-DPO| invented declined {p1:.2f} <= 0.05: {'holds' if out['P1'] else 'FAILS'}")
    print(f"P2 DPO < SFT invented declined ({A['OL_DPO']['invented_declined']} vs {A['OL_SFT']['invented_declined']}): {'holds' if out['P2'] else 'FAILS'}")
    print(f"P3 |RL-SFT| hard right <= 5 ({A['OL_RL']['hard_right']} vs {A['OL_SFT']['hard_right']}): {'holds' if out['P3'] else 'FAILS'}")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
