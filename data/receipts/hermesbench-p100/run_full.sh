#!/usr/bin/env bash
# Full 61-task HermesBench run: desktop drives, .73 serves.
# --timeout-overhead 300: P100 prompt processing is ~148 tok/s and 29 tool schemas push
# turn 1 to ~13k tokens (~83s) before a single output token. Default timeouts produce
# INFRA_ERRORs that look like model failures. See smoke01 (fail@90s) vs smoke02 (PASS@130s).
set -u
cd /home/mark/projects/hermes-bench-tool-call
RUN=full01
LOG=/home/mark/projects/hermes-bench-tool-call/${RUN}.log
echo "=== $(date -Is) START $RUN ===" >> "$LOG"
.venv/bin/python -m hermesbench run \
  --model "DavidAU-Fable-Fusion-711-MTP-Q6_K" \
  --base-url http://10.0.0.73:8082/v1 \
  --all --toolsets all \
  --timeout-overhead 300 \
  --run-id "$RUN" >> "$LOG" 2>&1
echo "=== $(date -Is) EXIT rc=$? ===" >> "$LOG"
echo "=== SIGNAL: hermesbench full01 done ===" >> "$LOG"
