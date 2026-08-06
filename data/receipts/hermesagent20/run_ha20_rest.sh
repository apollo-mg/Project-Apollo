#!/usr/bin/env bash
set -u
cd /home/mark/projects/HermesAgent-20
LOG=/home/mark/projects/HermesAgent-20/ha20_genesis_rest.log
echo "=== $(date -Is) START HA-04..HA-20 ===" >> "$LOG"
node scripts/run-scenarios.mjs  --scenario HA-04 --scenario HA-05 --scenario HA-06 --scenario HA-07 --scenario HA-08 --scenario HA-09 --scenario HA-10 --scenario HA-11 --scenario HA-12 --scenario HA-13 --scenario HA-14 --scenario HA-15 --scenario HA-16 --scenario HA-17 --scenario HA-18 --scenario HA-19 --scenario HA-20 \
  --model "Hermes3.6-35B-A3B-Genesis-V5-APEX" \
  --base-url http://10.0.0.73:8082/v1 \
  --auth-mode bearer --api-key "sk-local-llamacpp-noauth" \
  --json >> "$LOG" 2>&1
echo "=== $(date -Is) EXIT rc=$? ===" >> "$LOG"
echo "=== SIGNAL: ha20 rest done ===" >> "$LOG"
