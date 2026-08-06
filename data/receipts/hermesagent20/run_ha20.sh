#!/usr/bin/env bash
# HermesAgent-20 full run, pinned Hermes ea74f61d983e in Docker, model served from .73.
# Independent replication of the am423 hermes-bench three-way, on a PINNED harness.
set -u
cd /home/mark/projects/HermesAgent-20
MODEL="${1:-Hermes3.6-35B-A3B-Genesis-V5-APEX}"
TAG="${2:-genesis}"
LOG="/home/mark/projects/HermesAgent-20/ha20_${TAG}.log"
echo "=== $(date -Is) START $MODEL ===" >> "$LOG"
node scripts/run-scenarios.mjs --all \
  --model "$MODEL" \
  --base-url http://10.0.0.73:8082/v1 \
  --auth-mode bearer --api-key "sk-local-llamacpp-noauth" \
  --json >> "$LOG" 2>&1
echo "=== $(date -Is) EXIT rc=$? ===" >> "$LOG"
echo "=== SIGNAL: ha20 ${TAG} done ===" >> "$LOG"
