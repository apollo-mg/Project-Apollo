#!/usr/bin/env python3
"""EXPLORATORY (after the registered Think analysis, e9cb7fd9): per-item grade transitions between adjacent Think stages
(SFT -> DPO, DPO -> RL) for invented and hard items, and finished-only declining rates. Grades by the registered
bare-answer rule; "unfinished" = TRUNCATED / INVALID / NO-ANSWER. Usage: transitions_think.py [--out RESULT_transitions_think.json]"""
import argparse, collections, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "idk-lora")); from bare_rule import regrade  # noqa: E402
UNF = ("TRUNCATED", "INVALID", "NO-ANSWER")
def lab(g): return "unfinished" if g in UNF else {"ABSTAINED": "declined", "CORRECT": "right", "WRONG": "wrong"}[g]
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "RESULT_transitions_think.json")); a = ap.parse_args()
    items = {x["id"]: x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))}
    G = {arm: {r["id"]: lab(regrade(items[r["id"]], r)) for r in map(json.loads, open(QA / "raw" / f"main_{arm}.jsonl")) if "id" in r}
         for arm in ("TH_SFT", "TH_DPO", "TH_RL")}
    out = {"transitions": {}, "finished_only_invented_declined": {}}
    for x, y in (("TH_SFT", "TH_DPO"), ("TH_DPO", "TH_RL")):
        for k in "UH":
            c = collections.Counter((G[x][i], G[y][i]) for i in items if items[i]["arm"] == k)
            out["transitions"][f"{x}->{y} {k}"] = {f"{p}->{q}": n for (p, q), n in sorted(c.items())}
            print(f"{x} -> {y}, {'invented' if k == 'U' else 'hard'}:", out["transitions"][f"{x}->{y} {k}"])
    for arm, g in G.items():
        f = [i for i in items if items[i]["arm"] == "U" and g[i] != "unfinished"]
        d = sum(g[i] == "declined" for i in f); out["finished_only_invented_declined"][arm] = [d, len(f)]
        print(f"{arm}: invented declined {d} of {len(f)} finished ({d / len(f):.2f})")
    json.dump(out, open(a.out, "w"), indent=1)
if __name__ == "__main__":
    main()
