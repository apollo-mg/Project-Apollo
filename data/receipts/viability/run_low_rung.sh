#!/usr/bin/env bash
# Completes the effort ladder at card sampling: the `low` rung.
# Seeds 1001-1003 match the existing medium/xhigh reps so the three efforts pair by seed.
# Server must be the matched stack on .194 (see PREREG_A6_LOW_RUNG.md): binary 73a55486c,
# Qwen3.8-27B-Q6_K, -c 8192, -sm layer. run_fixture.py flushes+fsyncs per item.
set -u
HOST=${HOST:-http://10.0.0.194:8080}
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for REP in 1 2 3; do
  echo "######## effort=low rep=$REP  $(date -Iseconds)"
  $PY -u run_fixture.py --host "$HOST" --tier cal --effort low \
      --sampling card --seed $((1000 + REP)) \
      --jsonl "card_low_rep${REP}.jsonl"
  echo
done
echo "######## LOW RUNG DONE $(date -Iseconds)"
