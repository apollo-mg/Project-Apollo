#!/usr/bin/env python3
"""Join an arm run in shards (run_main.py --shard I/N, arms ARM.s0 .. ARM.s<N-1>) into raw/main_ARM.jsonl: the header
of shard 0 plus every shard's start time and shard spec, then the rows in corpus order. Refuses if a shard's
header fields other than arm/shard/meta/started/props differ, if an id repeats, or if the output already exists.
Usage: merge_shards.py ARM N"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
arm, n = sys.argv[1], int(sys.argv[2])
out = HERE / "raw" / f"main_{arm}.jsonl"
assert not out.exists(), f"{out} exists"
order = {json.loads(l)["id"]: k for k, l in enumerate(open(HERE / "corpus" / "M1.jsonl"))}
heads, rows = [], {}
for s in range(n):
    lines = [json.loads(l) for l in open(HERE / "raw" / f"main_{arm}.s{s}.jsonl")]
    heads.append(lines[0])
    for r in lines[1:]:
        assert r["id"] not in rows, f"duplicate {r['id']}"
        rows[r["id"]] = r
skip = {"arm", "shard", "meta", "started", "props"}
for h in heads[1:]:
    assert {k: v for k, v in h.items() if k not in skip} == {k: v for k, v in heads[0].items() if k not in skip}, "shard headers differ"
hdr = {**heads[0], "arm": arm, "shard": None, "shards": [{"shard": h["shard"], "started": h["started"], "meta": h["meta"]} for h in heads]}
with open(out, "w") as f:
    f.write(json.dumps(hdr, ensure_ascii=False) + "\n")
    for i in sorted(rows, key=order.get):
        f.write(json.dumps({**rows[i], "arm": rows[i].get("arm")}, ensure_ascii=False) + "\n")
print(f"{arm}: {len(rows)} rows from {n} shards -> {out.name}" + ("" if len(rows) == len(order) else f"  (MISSING {len(order) - len(rows)})"))
