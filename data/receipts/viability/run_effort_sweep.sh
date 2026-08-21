#!/usr/bin/env bash
# Effort sweep — tier_cal at each reasoning_effort level, same model, same items.
#
# AFM-23: reasoning_effort is consumed by the chat template, which injects system text.
#   xhigh  -> "validate key assumptions, consider plausible alternatives..."   (237 chars)
#   medium -> NOTHING                                                          (0 chars)
#   low    -> "keep your thinking brief... moving directly to the conclusion"   (166 chars)
# 'high' is excluded: the template silently rewrites it to xhigh.
#
# Every calibration number this project holds was produced at xhigh, i.e. with a near-direct
# instruction to check premises — the exact operation a false-premise item tests. This
# measures how much of the result belongs to the template rather than the model.
set -u
HOST=${HOST:-http://127.0.0.1:8080}
STAMP=$(date +%Y%m%d)
for EFF in medium low xhigh; do
  echo "############ reasoning_effort = $EFF  ($(date -Iseconds))"
  python3 -u run_fixture.py --host "$HOST" --tier cal --effort "$EFF" \
      --jsonl "sweep_rdna4_${EFF}_${STAMP}.jsonl"
  echo
done
echo "### sweep finished $(date -Iseconds)"
