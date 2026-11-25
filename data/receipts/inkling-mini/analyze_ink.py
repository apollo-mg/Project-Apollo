#!/usr/bin/env python3
"""Registered analysis for PREREG_INKLING_MINI.md: INK vs DR27_N73 (quant-abstention/raw/main_<ARM>.jsonl), bare-answer
rule; paired bootstrap over items, 10,000, seed 20261124. Usage: analyze_ink.py [--out RESULT_ink.json]"""
import argparse, json, statistics, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")
def load(arm, items):
    rows = {r["id"]: r for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
    for i, r in rows.items():
        if "content" in r: r["grade"] = regrade(items[i], r)
    return rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_ink.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    by = {k: sorted(i for i, x in items.items() if x["arm"] == k) for k in "EHU"}
    R = {"INK": load("INK", items), "DR27_N73": load("DR27_N73", items)}; out = {}
    for arm, r in R.items():
        g = {i: r[i]["grade"] for i in items}
        toks = [((r[i].get("gen_usage") or {}).get("completion_tokens")) for i in items]
        o = {"invented_declined": sum(g[i] == "ABSTAINED" for i in by["U"]), "hard_right": sum(g[i] == "CORRECT" for i in by["H"]),
             "hard_wrong": sum(g[i] not in ("CORRECT", "ABSTAINED") and g[i] not in UNF for i in by["H"]),
             "hard_declined": sum(g[i] == "ABSTAINED" for i in by["H"]), "easy_right": sum(g[i] == "CORRECT" for i in by["E"]),
             "invented_answered": sum(g[i] not in ("ABSTAINED",) and g[i] not in UNF for i in by["U"]),
             "unfinished": sum(g[i] in UNF for i in items),
             "median_tokens": statistics.median([t for t in toks if t is not None]) if any(t is not None for t in toks) else None,
             "max_tokens": max([t for t in toks if t is not None], default=None),
             "median_tps": statistics.median([r[i]["gen_tps"] for i in items if r[i].get("gen_tps")]) if any(r[i].get("gen_tps") for i in items) else None}
        out[arm] = o; print(arm, o)
    rng = np.random.default_rng(20261124)
    def paired(ids, f):
        d = np.array([f(R["INK"][i]) - f(R["DR27_N73"][i]) for i in ids], float); bs = d[rng.integers(0, len(d), (10000, len(d)))].mean(1)
        return round(float(d.mean()), 3), (round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3))
    t = {"invented_declined": paired(by["U"], lambda r: float(r["grade"] == "ABSTAINED")),
         "hard_right": paired(by["H"], lambda r: float(r["grade"] == "CORRECT")),
         "easy_right": paired(by["E"], lambda r: float(r["grade"] == "CORRECT"))}
    i, h = out["INK"]["invented_declined"], out["INK"]["hard_right"]
    t["H1"] = i < out["DR27_N73"]["invented_declined"]; t["H2a"] = h <= out["DR27_N73"]["hard_right"]; t["H2b"] = h >= 30
    out["tests"] = t; print("\nINK - DR27_N73:", {k: v for k, v in t.items() if not k.startswith("H")})
    print(f"H1 fewer invented declined than Qwen3.8-27B ({i} vs {out['DR27_N73']['invented_declined']}): {'holds' if t['H1'] else 'FAILS'}")
    print(f"H2a hard right at most Qwen's ({h} vs {out['DR27_N73']['hard_right']}): {'holds' if t['H2a'] else 'FAILS'}")
    print(f"H2b hard right at least 30 ({h}): {'holds' if t['H2b'] else 'FAILS'}")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
