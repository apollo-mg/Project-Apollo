#!/bin/bash
# PREREG_KMIC_VS_DAILY_73.md. Runs on the desktop; drives .73 over ssh. ./run_kmic.sh [CELL...]
# (default: MD1 MK1 MK2 MD2 MD0 D1 K1 K2 D2). The wake proxy must be stopped first: it would relaunch the daily
# server or suspend .73 mid-leg.
set -u
D=$(cd "$(dirname "$0")" && pwd); mkdir -p "$D/raw"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
systemctl --user is-active -q apollo-wake-proxy && { echo "ABORT: wake proxy is running"; exit 2; }
scp -q "$D/launch73.sh" 10.0.0.73:kmic73_launch.sh || exit 2
CELLS=${*:-MD1 MK1 MK2 MD2 MD0 D1 K1 K2 D2}
for CELL in $CELLS; do
  case $CELL in
    M*) MODE=micro; DEP="";;
    D1|K1) MODE=served; DEP=2k,32k,128k;;
    D2|K2) MODE=served; DEP=2k,32k;;
    *) echo "unknown cell $CELL"; continue;;
  esac
  echo "######## $CELL $(date -Is)"
  ssh 10.0.0.73 "bash ~/kmic73_launch.sh $CELL" || { echo "ABORT: launch failed"; exit 2; }
  timeout 7200 "$PY" "$D/kbench.py" $MODE "$CELL" "$D/raw/$CELL.jsonl" $DEP; rc=$?
  echo "   bench rc=$rc"
  ssh 10.0.0.73 "W=~/kmic73; P=\$(cat \$W/$CELL.pid); if kill -0 \$P 2>/dev/null; then echo ALIVE_AT_END; kill \$P; else echo DEAD_AT_END; fi; kill \$(cat \$W/$CELL.smipid) 2>/dev/null; for i in \$(seq 60); do kill -0 \$P 2>/dev/null || break; sleep 1; done; pgrep -x llama-server >/dev/null && echo STILL_RUNNING || echo stopped; echo abort_lines \$(grep -c -E 'ggml_abort|GGML_ASSERT|SIGABRT|Aborted|out of memory' \$W/$CELL.log)"
done
echo "######## CELLS DONE $(date -Is)"
