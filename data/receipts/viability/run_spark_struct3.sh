#!/usr/bin/env bash
set -u
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for REP in 1 2 3; do
  echo "######## true-fix rep=$REP $(date -Iseconds)"
  $PY -u run_fixture_structfix.py --host http://127.0.0.1:8086 --fixture fixture_struct_fixed.json \
      --tier struct --sampling card --seed $((1000+REP)) \
      --jsonl "sparktrue_rep${REP}.jsonl" 2>&1 | grep -aE "TS-0|    -> "
done
echo "######## TRUEFIX DONE $(date -Iseconds)"
