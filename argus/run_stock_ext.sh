#!/usr/bin/env bash
# Extend the STOCK Qwen3.8-27B arm from n=5 to n=12.
# Stock is the baseline every fine-tune comparison is measured against, and at n=5 it is our
# thinnest arm -- Cold-Fusion's 83% vs stock's 60% is partly just stock having fewer samples.
# Config MATCHED to repeats_t06.jsonl exactly: Q6_K, effort=medium, temp 0.6, top_p 0.95,
# top_k 20, min_p 0.0, repeat 1.0, presence 0.0. Same two scenarios as every other arm.
set -u
A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd "$A"
for i in $(seq 1 7); do
  echo "######## stock ext $i/7  $(date -Iseconds)"
  timeout 5000 $PY driver.py --transport gateway --base http://127.0.0.1:8645 \
      --fake-root $A/fixtures/ref/fake-google --scenarios runs/effort_probe.json \
      --out runs/stock_ext.jsonl --events runs/live_ref.jsonl --timeout 900 2>&1 | tail -4
done
echo "######## stock ext done $(date -Iseconds)"
