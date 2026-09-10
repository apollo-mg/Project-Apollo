#!/usr/bin/env bash
# tier_cal at the model's PUBLISHED sampling, with repeats.
#
# Every fixture number to date used greedy (temp 0 / top_k 1), which RETRACTION_NO_STOP.md
# showed is (a) not what this model is tuned for and (b) a direct cause of the NO-STOP
# signature we briefly mistook for a model property. Card thinking-mode sampling is
# NON-DETERMINISTIC, so a rate needs repeats — greedy never did.
#
# medium and xhigh both run: the effort sweep's only surviving claim is a COST ratio measured
# under greedy, and whether it holds at real sampling is open.
set -u
HOST=${HOST:-http://10.0.0.194:8080}
for EFF in medium xhigh; do
  for REP in 1 2 3; do
    echo "######## effort=$EFF rep=$REP  $(date -Iseconds)"
    python3 -u run_fixture.py --host "$HOST" --tier cal --effort "$EFF" \
        --sampling card --seed $((1000 + REP)) \
        --jsonl "card_${EFF}_rep${REP}.jsonl"
    echo
  done
done
echo "### finished $(date -Iseconds)"
