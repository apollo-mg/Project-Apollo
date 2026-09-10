#!/usr/bin/env bash
# Cold-Fusion vs base Q6_K on tier_cal. Same binary (llama_stock/build_puzzle) as the base
# baseline, same card sampling, same effort levels, 3 seeds — so the ONLY differences are the
# fine-tune and the NEO IMATRIX quant recipe (which cannot be separated).
#
# Pre-registered prediction (CF vs base):
#   confabulation on CAL-U*  RISES   — the deliberation that catches false premises is shortened
#   answerable accuracy      HOLDS 8/8 — accuracy is not the fragile part
#   runaway rate             FALLS   — the fine-tune doing what it advertises
set -u
HOST=${HOST:-http://10.0.0.194:8081}
for EFF in medium xhigh; do
  for REP in 1 2 3; do
    echo "######## coldfusion effort=$EFF rep=$REP  $(date -Iseconds)"
    python3 -u run_fixture.py --host "$HOST" --tier cal --effort "$EFF" \
        --sampling card --seed $((1000 + REP)) \
        --jsonl "cf_${EFF}_rep${REP}.jsonl"
    echo
  done
done
echo "### finished $(date -Iseconds)"
