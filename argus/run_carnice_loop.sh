#!/usr/bin/env bash
# 12 repeats only -- the Carnice server on .194:8084 is already up and /props-verified.
set -u
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd /mnt/TG_2TB/Projects/Apollo/argus
for i in $(seq 1 12); do
  echo "######## carnice-rerun $i/12  $(date -Iseconds)"
  timeout 4000 $PY driver.py --transport gateway --scenarios runs/effort_probe.json \
      --out runs/carnice_rerun.jsonl --events runs/live_carnice_rerun.jsonl --timeout 1800 2>&1 | tail -4
done
echo "######## carnice-rerun done $(date -Iseconds)"
