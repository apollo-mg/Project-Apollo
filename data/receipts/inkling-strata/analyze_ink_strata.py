#!/usr/bin/env python3
"""Registered analysis for PREREG_INKLING_STRATA.md: S1, S2 (INKS10 vs INKS20), S3 (INKS20 vs INK), paired bootstrap over
items, 10,000, seed 20261127; DR27_N73 for context. Usage: analyze_ink_strata.py [--out RESULT_ink_strata.json]"""
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
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_ink_strata.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in "EHU"}
    R = {arm: load(arm, items) for arm in ("INKS20", "INKS20V2", "INKS10", "INK", "DR27_N73")}; out = {"arms": {}}
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
    for x, y in (("INKS10", "INKS20"), ("INKS20V2", "INKS20"), ("INKS20", "INK"), ("INKS20", "DR27_N73")):
        out[f"{x}-{y}"] = {"invented_declined": paired(x, y, by["U"], lambda r: float(r["grade"] == "ABSTAINED")),
                           "invented_answered": paired(x, y, by["U"], lambda r: float(r["grade"] not in UNF and r["grade"] != "ABSTAINED")),
                           "hard_right": paired(x, y, by["H"], lambda r: float(r["grade"] == "CORRECT")),
                           "hard_declined": paired(x, y, by["H"], lambda r: float(r["grade"] == "ABSTAINED")),
                           "easy_right": paired(x, y, by["E"], lambda r: float(r["grade"] == "CORRECT"))}
        print(f"{x} minus {y}:", out[f"{x}-{y}"])
    A = out["arms"]
    out["S1"] = A["INKS10"]["invented_declined"] < A["INKS20"]["invented_declined"]
    out["S2"] = A["INKS10"]["hard_right"] <= A["INKS20"]["hard_right"]
    out["S3"] = A["INKS20"]["invented_declined"] < A["INK"]["invented_declined"]
    print(f"S1 INKS10 declines fewer invented ({A['INKS10']['invented_declined']} vs {A['INKS20']['invented_declined']}): {'holds' if out['S1'] else 'FAILS'}")
    print(f"S2 INKS10 hard right <= INKS20 ({A['INKS10']['hard_right']} vs {A['INKS20']['hard_right']}): {'holds' if out['S2'] else 'FAILS'}")
    print(f"S3 INKS20 declines fewer invented than INK ({A['INKS20']['invented_declined']} vs {A['INK']['invented_declined']}): {'holds' if out['S3'] else 'FAILS'}")
    same = sum(R["INKS20V2"][i]["content"] == R["INKS20"][i]["content"] for i in items)
    out["v2_same_text"] = same; print(f"INKS20V2 vs INKS20 same answer text: {same}/240")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
