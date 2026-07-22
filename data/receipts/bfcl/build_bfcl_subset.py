#!/usr/bin/env python3
"""Build a seed-pinned, stratified ~200-item BFCL AST subset for the matched
Puzzle-Q4 vs Qwen-Q8 comparison. Same IDs used for BOTH models (paired -> McNemar).

Proportional to the full non-live AST category sizes (399,99,49,199,199,199 = 1144),
scaled to ~200. Writes BFCL's native test_case_ids_to_generate.json so the stock
`bfcl generate --run-ids` runs exactly these IDs (canonical harness, official scorer).
"""
import json, random, os
import bfcl_eval
from bfcl_eval.constants.eval_config import TEST_IDS_TO_GENERATE_PATH, PROJECT_ROOT
EXAMPLE = os.path.join(os.path.dirname(bfcl_eval.__file__), "test_case_ids_to_generate.json.example")

SEED = 42
# proportional-to-full-set counts, sum = 201
TARGET = {
    "simple_python": 70,
    "simple_java": 17,
    "simple_javascript": 9,
    "multiple": 35,
    "parallel": 35,
    "parallel_multiple": 35,
}
import pathlib
DATA = pathlib.Path(os.path.dirname(bfcl_eval.__file__)) / "data"

def ids_for(cat):
    f = DATA / f"BFCL_v4_{cat}.json"
    ids = []
    with open(f) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ids.append(json.loads(line)["id"])
    return ids

rng = random.Random(SEED)
# full 24-category skeleton (all empty), then fill our 6 — matches the .example structure
skeleton = json.load(open(EXAMPLE))
for k in skeleton:
    skeleton[k] = []

chosen = {}
for cat, n in TARGET.items():
    allids = sorted(ids_for(cat))          # sort first for determinism regardless of file order
    pick = sorted(rng.sample(allids, n))
    skeleton[cat] = pick
    chosen[cat] = pick

json.dump(skeleton, open(TEST_IDS_TO_GENERATE_PATH, "w"), indent=2)
total = sum(len(v) for v in chosen.values())
print(f"seed={SEED}  total items={total}")
for cat in TARGET:
    print(f"  {cat:20s} {len(chosen[cat]):3d} / {len(ids_for(cat))}")
print(f"wrote {TEST_IDS_TO_GENERATE_PATH}")

# save a reproducible manifest alongside (seed + full id list + counts)
manifest = {"seed": SEED, "targets": TARGET, "total": total,
            "bfcl_version": "2026.3.23", "chosen_ids": chosen}
mpath = "/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/bfcl_subset_manifest.json"
json.dump(manifest, open(mpath, "w"), indent=2)
print("manifest ->", mpath)
