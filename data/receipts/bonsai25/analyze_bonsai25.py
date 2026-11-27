#!/usr/bin/env python3
"""Registered analysis for PREREG_BONSAI25.md: G1 (BON2R vs BONB9 answer text), H1, H2 (BON25 vs BON2R), paired
bootstrap over items, 10,000, seed 20261127; DR27_N73 for context. Usage: analyze_bonsai25.py [--out RESULT_bonsai25.json]"""
import argparse, json, statistics, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")
def load(arm, items):
    rows = {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
    if set(items) - set(rows): sys.exit(f"{arm}: {len(set(items) - set(rows))} items missing")
    for i, r in rows.items(): r["grade"] = regrade(items[i], r)
    return rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_bonsai25.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in "EHU"}
    R = {arm: load(arm, items) for arm in ("BONB9", "BON2R", "BON25", "DR27_N73")}; out = {"arms": {}}
    same = sum(R["BON2R"][i]["content"] == R["BONB9"][i]["content"] for i in items)
    out["G1_same_text"] = same; out["G1"] = same >= 238
    print(f"G1 BON2R vs BONB9 same answer text: {same}/240 -> {'PASS' if out['G1'] else 'FAIL'}")
    for arm, r in R.items():
        g = {i: r[i]["grade"] for i in items}
        toks = [((r[i].get("gen_usage") or {}).get("completion_tokens")) for i in items]
        pu = [r[i]["P_abs"] for i in by["U"] if r[i].get("P_abs") is not None]
        out["arms"][arm] = o = {
            "invented_declined": sum(g[i] == "ABSTAINED" for i in by["U"]),
            "invented_answered": sum(g[i] not in UNF and g[i] != "ABSTAINED" for i in by["U"]),
            "hard_right": sum(g[i] == "CORRECT" for i in by["H"]), "hard_wrong": sum(g[i] == "WRONG" for i in by["H"]),
            "hard_declined": sum(g[i] == "ABSTAINED" for i in by["H"]), "easy_right": sum(g[i] == "CORRECT" for i in by["E"]),
            "unfinished": sum(g[i] in UNF for i in items),
            "median_tokens": statistics.median([t for t in toks if t is not None]) if any(t is not None for t in toks) else None,
            "mean_slot_p_unknown_invented": round(statistics.mean(pu), 3) if pu else None}
        print(f"{arm}:", o)
    rng = np.random.default_rng(20261127)
    def paired(x, y, ids, f):
        d = np.array([f(R[x][i]) - f(R[y][i]) for i in ids], float); bs = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
        return round(float(d.mean()), 3), (round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3))
    out["BON25-BON2R"] = {"invented_declined": paired("BON25", "BON2R", by["U"], lambda r: float(r["grade"] == "ABSTAINED")),
                          "invented_answered": paired("BON25", "BON2R", by["U"], lambda r: float(r["grade"] not in UNF and r["grade"] != "ABSTAINED")),
                          "hard_right": paired("BON25", "BON2R", by["H"], lambda r: float(r["grade"] == "CORRECT")),
                          "hard_declined": paired("BON25", "BON2R", by["H"], lambda r: float(r["grade"] == "ABSTAINED")),
                          "easy_right": paired("BON25", "BON2R", by["E"], lambda r: float(r["grade"] == "CORRECT")),
                          "slot_p_unknown_invented": paired("BON25", "BON2R", by["U"], lambda r: float(r["P_abs"] or 0))}
    print("BON25 minus BON2R:", out["BON25-BON2R"])
    A = out["arms"]
    out["H1"] = A["BON25"]["invented_declined"] < A["BON2R"]["invented_declined"]
    out["H2"] = abs(A["BON25"]["hard_right"] - A["BON2R"]["hard_right"]) <= 5
    print(f"H1 BON25 declines fewer invented ({A['BON25']['invented_declined']} vs {A['BON2R']['invented_declined']}): {'holds' if out['H1'] else 'FAILS'}")
    print(f"H2 hard right within 5 ({A['BON25']['hard_right']} vs {A['BON2R']['hard_right']}): {'holds' if out['H2'] else 'FAILS'}")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
