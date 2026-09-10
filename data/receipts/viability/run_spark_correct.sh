#!/usr/bin/env bash
# Spark-X2.5-4B tier_cal at ITS OWN card sampling: temperature=1.0, top_p=0.95, top_k=-1.
# The earlier arm (RESULT_SPARK4B_TIERCAL.md) used top_k=20 -- Qwen3.8's card value, inherited
# from run_fixture.py's hardcoded "card" preset. Same seeds so the arms pair.
set -u
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for REP in 1 2 3; do
  echo "######## spark_card rep=$REP $(date -Iseconds)"
  $PY -u run_fixture_structfix.py --host http://127.0.0.1:8086 --tier cal \
      --effort medium --sampling spark_card --seed $((1000+REP)) \
      --jsonl "sparkcard_rep${REP}.jsonl" 2>&1 | grep -aE "sampling =|-> " | head -3
done
echo "######## SPARK CARD DONE $(date -Iseconds)"
