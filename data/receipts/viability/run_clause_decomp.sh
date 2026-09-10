#!/usr/bin/env bash
# Clause decomposition of the xhigh instruction. See PREREG_CLAUSE_DECOMP.md.
# All arms run at --effort medium (0-char system block); the clause text is carried in
# tier_cal.prompt of the generated fixture copies, so run_fixture.py is unmodified.
set -u
HOST=${HOST:-http://10.0.0.194:8080}
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for ARM in full validate alternatives; do
  for REP in 1 2 3; do
    echo "######## clause=$ARM rep=$REP  $(date -Iseconds)"
    $PY -u run_fixture.py --host "$HOST" --fixture "fixture_clause_${ARM}.json" \
        --tier cal --effort medium --sampling card --seed $((1000 + REP)) \
        --jsonl "clause_${ARM}_rep${REP}.jsonl"
    echo
  done
done
echo "######## CLAUSE DECOMP DONE $(date -Iseconds)"
