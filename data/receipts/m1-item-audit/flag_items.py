#!/usr/bin/env python3
"""M1 item audit, step 1: flag the items whose failures look like a problem with the item, not the models.
Read-only over stored answers: one primary greedy thinking-off arm per model (a family with many quants counts once).
  Real items (easy, hard): flagged when the most common WRONG answer is given by >= K models (a consensus against the
    key), or when no model is graded correct.
  Invented items: flagged when one specific answer (not UNKNOWN) is given by >= K models (a consensus that the thing
    exists, so it might).
Writes flags.json beside this file. Usage: flag_items.py [--k 6]"""
import argparse, json, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "viability"))
from run_fixture import bare  # noqa: E402  (the grader's own normaliser)

REG = json.load(open(HERE.parents[1] / "scorecard" / "registry.json"))
ITEMS = {json.loads(l)["id"]: json.loads(l) for l in open(QA / "corpus" / "M1.jsonl")}


def main(k):
    arms = {}
    for a, v in REG["m1_arms"].items():
        if v.get("primary") and v.get("thinking") == "off" and (QA / "raw" / f"main_{a}.jsonl").exists():
            arms.setdefault(v["model"], a)
    rows = defaultdict(list)
    for model, arm in arms.items():
        for line in open(QA / "raw" / f"main_{arm}.jsonl"):
            r = json.loads(line)
            if "id" in r:
                rows[r["id"]].append({"model": model, "got": r.get("got") or "", "grade": r.get("grade_lenient") or r.get("grade")})
    flags = []
    for i, rs in sorted(rows.items()):
        it = ITEMS[i]
        if it["arm"] == "U":
            c = Counter(bare(r["got"]) for r in rs if r["grade"] == "WRONG" and bare(r["got"]))
            top = c.most_common(1)
            if top and top[0][1] >= k:
                flags.append({"id": i, "group": "invented", "why": f"{top[0][1]} of {len(rs)} models name the same answer", "consensus": top[0][0]})
        else:
            right = sum(r["grade"] == "CORRECT" for r in rs)
            c = Counter(bare(r["got"]) for r in rs if r["grade"] == "WRONG" and bare(r["got"]))
            top = c.most_common(1)
            if (top and top[0][1] >= k) or right == 0:
                flags.append({"id": i, "group": {"E": "easy", "H": "hard"}[it["arm"]], "gold": it["gold"], "correct": right,
                              "n": len(rs), "consensus": top[0][0] if top else None, "consensus_n": top[0][1] if top else 0,
                              "why": "consensus against the key" if top and top[0][1] >= k else "no model correct"})
    out = {"models": len(arms), "k": k, "flags": flags}
    (HERE / "flags.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{len(arms)} models; {len(flags)} items flagged (k = {k})")
    for f in flags:
        it = ITEMS[f["id"]]
        print(f"  {f['id']:14} {f['group']:8} {f['why']:28} gold={f.get('gold', 'UNKNOWN')!r:22} consensus={f['consensus']!r} "
              f"{('(' + str(f['consensus_n']) + ')') if 'consensus_n' in f else ''} correct={f.get('correct', '-')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--k", type=int, default=6)
    main(ap.parse_args().k)
