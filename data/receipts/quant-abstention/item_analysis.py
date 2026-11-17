#!/usr/bin/env python3
"""M1 item analysis: for each item, the share of models that got it right (real items) or declined it (invented
items), one primary greedy thinking-off arm per model so a family with many quants counts once; the items most models
fail, the mean by template, and the answers the models gave instead (the "distractors"). Exploratory, read-only.
Usage: item_analysis.py [--show ID ...]"""
import argparse, json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
REG = json.load(open(HERE.parents[1] / "scorecard" / "registry.json"))
ITEMS = {json.loads(l)["id"]: json.loads(l) for l in open(HERE / "corpus" / "M1.jsonl")}


def arms():
    out = {}
    for a, v in REG["m1_arms"].items():
        if v.get("primary") and v.get("thinking") == "off" and (RAW / f"main_{a}.jsonl").exists():
            out.setdefault(v["model"], a)
    return out


def main(a):
    ok, answers = defaultdict(list), defaultdict(Counter)
    am = arms()
    for model, arm in am.items():
        for line in open(RAW / f"main_{arm}.jsonl"):
            r = json.loads(line)
            if "id" not in r:
                continue
            g = r.get("grade_lenient") or r.get("grade")
            ok[r["id"]].append(g == "ABSTAINED" if ITEMS[r["id"]]["arm"] == "U" else g == "CORRECT")
            answers[r["id"]][(r.get("got") or "-")[:28]] += 1
    rate = {i: sum(v) / len(v) for i, v in ok.items()}
    print(f"{len(am)} models, one primary arm each\n")
    for group, title in (("U", "invented, share that declined"), ("H", "hard real, share correct"), ("E", "easy real, share correct")):
        ids = sorted((i for i in rate if ITEMS[i]["arm"] == group), key=lambda i: rate[i])
        by = defaultdict(list)
        for i in ids:
            by[ITEMS[i]["template"]].append(rate[i])
        print(f"== {title}; by template: " + ", ".join(f"{t} {sum(v) / len(v):.2f}" for t, v in sorted(by.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))))
        for i in ids[: a.k]:
            print(f"  {rate[i]:.2f}  {i:14} gold={ITEMS[i]['gold'][:24]!r:28} answers: " + ", ".join(f"{k} x{n}" for k, n in answers[i].most_common(4)))
        print()
    for i in a.show:
        print(f"{i}: {ITEMS[i]['question']}\n   gold {ITEMS[i]['gold']!r}; answers: " + ", ".join(f"{k} x{n}" for k, n in answers[i].most_common(8)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--k", type=int, default=6); ap.add_argument("--show", nargs="*", default=[])
    main(ap.parse_args())
