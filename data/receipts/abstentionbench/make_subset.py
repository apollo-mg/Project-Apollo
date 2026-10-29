#!/usr/bin/env python3
"""AbstentionBench-sub500 (PREREG_ABENCH_SUBSET.md): a frozen, stratified subset of the 2,004-item fast subset. Selection
reads only dataset, index, should_abstain and a hash of the question text from fast_subset.jsonl, never a model verdict.

Cells are (dataset, should_abstain). Quotas are proportional to cell size by largest remainder, at least 1 per cell. Within
a cell, items are ranked by sha256("SEED:dataset:index") and the first `quota` are taken, so a larger N reuses the same
ranking (containment is asserted, not assumed). Writes subset_<N>.csv: dataset, index, should_abstain, q_sha256 (a hash,
never item text: GPQA rule). Prints each card metric's n and its worst-case 95 % Wilson half-width.

Usage: make_subset.py ITEMS.jsonl [--n 500] [--nested 1000] [--write]
       make_subset.py ITEMS.jsonl --verify subset_500.csv [--emit OUT.jsonl]   (refuse on any question-hash mismatch;
                                                                                 --emit writes the subset items with text,
                                                                                 for run_abench.py, outside the repo)"""
import argparse, csv, hashlib, json, math, sys
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
SEED = 20261028
MISSING_INFO = {"GSM8K", "MMLUMath", "MMLUHistory", "GPQA"}; FALSE_PREMISE = {"FalseQADataset", "QAQADataset"}   # as build_scorecard.py


def qhash(q): return hashlib.sha256(q.encode("utf-8")).hexdigest()
def rank(d, i): return hashlib.sha256(f"{SEED}:{d}:{i}".encode()).hexdigest()


def select(items, n):
    cells = defaultdict(list)
    for it in items: cells[(it["dataset"], bool(it["should_abstain"]))].append(it)
    total = len(items); exact = {c: n * len(v) / total for c, v in cells.items()}
    quota = {c: max(1, math.floor(x)) for c, x in exact.items()}
    for c in sorted(cells, key=lambda c: (-(exact[c] - math.floor(exact[c])), c))[: n - sum(quota.values())]: quota[c] += 1
    assert sum(quota.values()) == n, (sum(quota.values()), n)
    return [it for c, v in sorted(cells.items()) for it in sorted(v, key=lambda it: rank(it["dataset"], it["index"]))[: quota[c]]]


def wilson_half(n, z=1.96):   # worst case, p = 0.5
    return z * math.sqrt(0.25 / n + z * z / (4 * n * n)) / (1 + z * z / n) if n else float("nan")


def resolution(sub):
    sa = [it for it in sub if it["should_abstain"]]
    rows = [("abstention recall", len(sa)), ("missing-info recall", sum(it["dataset"] in MISSING_INFO for it in sa)),
            ("false-premise recall", sum(it["dataset"] in FALSE_PREMISE for it in sa))]
    for name, k in rows: print(f"  {name:22s} n={k:4d}  worst-case 95% half-width +-{wilson_half(k):.3f}")
    print("  abstention precision   n = the model's own abstentions (not fixed by the design)")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("items"); ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--nested", type=int, default=1000); ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify"); ap.add_argument("--emit"); a = ap.parse_args()
    items = [json.loads(l) for l in open(a.items)]
    if a.verify:
        want = {(r["dataset"], r["index"]): r for r in csv.DictReader(open(a.verify))}
        have = {(it["dataset"], str(it["index"])): it for it in items}
        bad = [k for k, r in want.items() if k not in have or qhash(have[k]["question"]) != r["q_sha256"]
               or str(int(bool(have[k]["should_abstain"]))) != r["should_abstain"]]
        if bad: sys.exit(f"REFUSED: {len(bad)} of {len(want)} subset items missing or changed (first: {bad[:3]})")
        print(f"verified: {len(want)} subset items match their frozen question hashes and labels")
        if a.emit:
            with open(a.emit, "w") as f:
                for k in want: f.write(json.dumps(have[k], ensure_ascii=False) + "\n")
            print("wrote", a.emit)
        return
    sub, big = select(items, a.n), select(items, a.nested)
    key = lambda s: {(it["dataset"], it["index"]) for it in s}
    assert key(sub) <= key(big), f"subset_{a.n} is not contained in subset_{a.nested}"
    print(f"subset_{a.n}: {len(sub)} items, {sum(it['should_abstain'] for it in sub)} should-abstain; contained in subset_{a.nested}: yes")
    resolution(sub); print(f"subset_{a.nested} (registered fallback):"); resolution(big)
    if a.write:
        for n, s in ((a.n, sub), (a.nested, big)):
            with open(HERE / f"subset_{n}.csv", "w", newline="") as f:
                w = csv.writer(f); w.writerow(["dataset", "index", "should_abstain", "q_sha256"])
                for it in sorted(s, key=lambda it: (it["dataset"], it["index"])):
                    w.writerow([it["dataset"], it["index"], int(bool(it["should_abstain"])), qhash(it["question"])])
            print("wrote", f"subset_{n}.csv")


if __name__ == "__main__":
    main()
