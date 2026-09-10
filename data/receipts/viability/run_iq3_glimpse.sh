#!/usr/bin/env bash
# IQ3 glimpse on the 9070 XT. See PREREG_IQ3_RDNA4_GLIMPSE.md -- deliberately confounded
# (quant + hardware + backend + packager all differ from the Q6_K reference). Informative
# only if abstention HOLDS; a degradation is uninformative on cause.
# Both effort levels: the reference headline is the medium-vs-xhigh GAP, which is more
# robust to those confounds than either absolute number.
set -u
HOST=${HOST:-http://127.0.0.1:8085}
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
for EFF in medium xhigh; do
  for REP in 1 2 3; do
    echo "######## iq3 effort=$EFF rep=$REP  $(date -Iseconds)"
    $PY -u run_fixture.py --host "$HOST" --tier cal --effort "$EFF" \
        --sampling card --seed $((1000 + REP)) \
        --jsonl "iq3_${EFF}_rep${REP}.jsonl"
    echo
  done
done
echo "######## IQ3 GLIMPSE DONE $(date -Iseconds)"
