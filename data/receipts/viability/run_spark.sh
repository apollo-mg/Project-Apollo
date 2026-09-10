#!/usr/bin/env bash
# Spark-X2.5-4B on tier_cal. See PREREG_SPARK4B.md. Template ignores reasoning_effort
# (verified by rendering), so --effort medium is the no-injected-instruction baseline,
# matching how Qwen3.8-27B's medium arm ran.
set -u
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for REP in 1 2 3; do
  echo "######## spark rep=$REP  $(date -Iseconds)"
  $PY -u run_fixture.py --host http://127.0.0.1:8086 --tier cal --effort medium \
      --sampling card --seed $((1000 + REP)) --jsonl "spark_rep${REP}.jsonl" 2>&1 | tail -3
done
echo "######## SPARK DONE $(date -Iseconds)"
