#!/usr/bin/env python3
"""Rebuild humanevalplus.jsonl (the exact dataset revision these receipts were produced with).

The dataset is not vendored here (11.3 MB). This script re-fetches it and verifies it against
byte-count fingerprints measured from the original file, so a rebuilt copy can be proven
identical to the one used for the Puzzle / Laguna legs.

Usage:  python3 fetch_dataset.py [outdir]     (stdlib only, no `datasets` install needed)
"""
import json, urllib.request, sys, os

BASE = ("https://datasets-server.huggingface.co/rows"
        "?dataset=evalplus%2Fhumanevalplus&config=default&split=test")
COLS = ["task_id", "prompt", "canonical_solution", "entry_point", "test"]

# Fingerprints of the dataset used for the runs in SUMMARY.md.
FINGERPRINTS = {
    "n_problems":       164,
    "total_test_bytes": 10_730_825,
    "file_bytes":       11_317_638,
    "HumanEval/0":      77_039,
    "HumanEval/32":     55_505,
    "HumanEval/76":     21_930,
}

def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(outdir, "humanevalplus.jsonl")

    rows = []
    for off, ln in [(0, 100), (100, 64)]:          # rows API caps length at 100
        with urllib.request.urlopen(f"{BASE}&offset={off}&length={ln}", timeout=120) as r:
            rows += [x["row"] for x in json.loads(r.read())["rows"]]

    with open(path, "w") as f:
        for r in sorted(rows, key=lambda x: int(x["task_id"].split("/")[1])):
            f.write(json.dumps({k: r[k] for k in COLS}) + "\n")

    recs = [json.loads(l) for l in open(path)]
    by   = {r["task_id"]: r for r in recs}
    got  = {"n_problems": len(recs),
            "total_test_bytes": sum(len(r["test"]) for r in recs),
            "file_bytes": os.path.getsize(path),
            **{t: len(by[t]["test"]) for t in ("HumanEval/0", "HumanEval/32", "HumanEval/76")}}

    ok = True
    for k, want in FINGERPRINTS.items():
        match = got[k] == want
        ok &= match
        print(f"  {'OK ' if match else 'MISMATCH'} {k}: got={got[k]:,} want={want:,}")

    print("\n" + ("IDENTICAL to the dataset used for these receipts." if ok else
                  "DIFFERENT revision — results are NOT directly comparable to SUMMARY.md."))
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
