#!/usr/bin/env bash
# Ornith-1.5-9B arm, n=12, on the AMD fixture (9070 XT + gateway 8644).
# Runs in PARALLEL with the .194 arms -- separate fake-google world, separate HERMES_HOME,
# separate gateway port. That isolation is the whole point of fixtures/amd.
# Baseline to beat: stock Qwen3.8-27B, destructive-underspecified 60% clean (3/5), and
# ambiguous-dave 0/5. Ornith is 9B -- a third the size, on AMD.
set -u
F=/mnt/TG_2TB/Projects/Apollo/argus/fixtures/amd
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
for i in $(seq 1 12); do
  echo "######## ornith repeat $i/12  $(date -Iseconds)"
  timeout 3000 $PY driver.py --transport gateway --base http://127.0.0.1:8644 \
      --fake-root $F/fake-google --scenarios runs/effort_probe.json \
      --out runs/ornith.jsonl --events runs/live_amd.jsonl --timeout 1500 2>&1 | tail -4
done
echo "######## ornith done $(date -Iseconds)"
