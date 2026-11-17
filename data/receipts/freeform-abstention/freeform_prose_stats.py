#!/usr/bin/env python3
"""DESIGN_FREEFORM_ABSTENTION.md, section 5: what the existing M1 replies offer as DEVELOPMENT text for a free-text
reader. Descriptive only; nothing is fitted. For the development families (everything in the registry except the
held-out families below), per registered grade: how many replies carry prose before the last `Exact Answer:` line,
and how much of that prose repeats the offered word or the line's label (text written under a prompt that offers
UNKNOWN is not unprompted text).
Usage: freeform_prose_stats.py"""
import json, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "quant-abstention" / "raw"
REG = json.load(open(HERE.parents[1] / "scorecard" / "registry.json"))
HELD_OUT = {"qwen3.6-35b-a3b", "qwen3.5-9b", "llama-3.1-8b", "granite-4.1-3b"}      # fixed 2026-11-17, by family
ANS = re.compile(r"Exact Answer\s*:\s*(.+?)(?:\n|$)", re.I | re.S)


def family(model):
    return REG["models"].get(model, {}).get("lineage") or model


def main():
    arms = {a: v["model"] for a, v in REG["m1_arms"].items()}
    dev = sorted(a for a, m in arms.items() if family(m) not in HELD_OUT and (RAW / f"main_{a}.jsonl").exists())
    held = sorted(a for a, m in arms.items() if family(m) in HELD_OUT and (RAW / f"main_{a}.jsonl").exists())
    fams = Counter(family(arms[a]) for a in dev)
    print(f"development: {len(dev)} arm files, {len(fams)} families; held out: {len(held)} arm files "
          f"({', '.join(sorted({family(arms[a]) for a in held}))}); files not in the registry are unused")
    by = defaultdict(lambda: Counter()); lens = defaultdict(list)
    for a in dev:
        for line in open(RAW / f"main_{a}.jsonl"):
            r = json.loads(line)
            if "grade" not in r or r.get("content") is None:
                continue
            t = r["content"]; m = list(ANS.finditer(t))
            prose = (t[:m[-1].start()] if m else t).strip()
            g = r["grade"]; by[g]["n"] += 1
            if len(prose) >= 20:
                by[g]["prose"] += 1; lens[g].append(len(prose))
                by[g]["says_unknown"] += bool(re.search(r"\bunknown\b", prose, re.I))
                by[g]["echoes_label"] += bool(re.search(r"exact answer", prose, re.I))
    print("| registered grade | replies | with prose (>= 20 chars) | median prose chars | prose says 'unknown' | prose repeats 'Exact Answer' |")
    print("|---|---:|---:|---:|---:|---:|")
    for g in sorted(by, key=lambda k: -by[k]["n"]):
        c = by[g]; p = max(c["prose"], 1)
        print(f"| {g} | {c['n']} | {c['prose']} ({c['prose'] / c['n']:.0%}) | {statistics.median(lens[g]) if lens[g] else 0:.0f} | "
              f"{c['says_unknown']} ({c['says_unknown'] / p:.0%}) | {c['echoes_label']} ({c['echoes_label'] / p:.0%}) |")


if __name__ == "__main__":
    main()
