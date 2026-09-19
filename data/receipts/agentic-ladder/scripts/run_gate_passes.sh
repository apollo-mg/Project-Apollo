#!/usr/bin/env bash
# P-A0: two passes of ONE arm through the v1 pool. Determinism at temp 0 is the question.
# World is reset to seed before every scenario by the driver itself.
set -u
ARM="${1:?}"; A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
R=/mnt/TG_2TB/Projects/Apollo/data/receipts/agentic-ladder
cd "$A"
echo "seed sha256: $(sha256sum fake-google/fixtures/seed.json | cut -c1-32)" | tee -a "$R/logs/gate_${ARM}.log"
for p in 1 2; do
  echo "######## $ARM pass $p/2  $(date -Iseconds)" | tee -a "$R/logs/gate_${ARM}.log"
  rm -f "runs/gate_${ARM}_p${p}.jsonl"
  timeout 3600 $PY driver.py --transport gateway --base http://127.0.0.1:8643 \
    --fake-root "$A/fake-google" --scenarios scenarios_v1_pool_gate.json \
    --out "runs/gate_${ARM}_p${p}.jsonl" --events "runs/live_gate_${ARM}_p${p}.jsonl" \
    --timeout 600 >> "$R/logs/gate_${ARM}.log" 2>&1
  echo "   pass $p rc=$? rows=$(wc -l < runs/gate_${ARM}_p${p}.jsonl 2>/dev/null || echo 0)" | tee -a "$R/logs/gate_${ARM}.log"
done
echo "######## GATE PASSES DONE $(date -Iseconds)" | tee -a "$R/logs/gate_${ARM}.log"
