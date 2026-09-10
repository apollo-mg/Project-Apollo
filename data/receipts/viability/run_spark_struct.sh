#!/usr/bin/env bash
# tier_struct against Spark-X2.5-4B with n_predict raised 3072 -> 7168. The default budget
# VOIDs on this model: it auto-opens <think> every turn and truncates before emitting JSON.
# That is a budget artifact, not a JSON-capability result.
set -u
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for REP in 1 2 3; do
  echo "######## struct-big rep=$REP $(date -Iseconds)"
  $PY -u run_fixture.py --host http://127.0.0.1:8086 --fixture fixture_struct_bigbudget.json \
      --tier struct --sampling card --seed $((1000+REP)) \
      --jsonl "sparkstruct_rep${REP}.jsonl" 2>&1 | grep -aE "TS-0|->|TIER"
done
echo "######## STRUCT BIG DONE $(date -Iseconds)"
