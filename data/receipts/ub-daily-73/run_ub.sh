#!/bin/bash
# PREREG_UB_DAILY_73.md. Runs on the desktop; drives .73 over ssh. ./run_ub.sh [CELL...] (default: U512 U2048 U1024)
# The wake proxy must be stopped first: it would relaunch the daily server or suspend .73 mid-leg.
set -u
D=$(cd "$(dirname "$0")" && pwd); mkdir -p "$D/raw"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
systemctl --user is-active -q apollo-wake-proxy && { echo "ABORT: wake proxy is running"; exit 2; }
scp -q "$D/launch73_ub.sh" 10.0.0.73:ub73_launch.sh || exit 2
CELLS=${*:-U512 U2048 U1024}
for CELL in $CELLS; do
  echo "######## $CELL $(date -Is)"
  ssh 10.0.0.73 "bash ~/ub73_launch.sh $CELL" || { echo "ABORT: launch failed"; exit 2; }
  timeout 7200 "$PY" "$D/ubbench.py" "$CELL" "$D/raw/$CELL.jsonl"; rc=$?
  echo "   bench rc=$rc"
  ssh 10.0.0.73 "W=~/ub73; P=\$(cat \$W/$CELL.pid); if kill -0 \$P 2>/dev/null; then echo ALIVE_AT_END; kill \$P; else echo DEAD_AT_END; fi; kill \$(cat \$W/$CELL.smipid) 2>/dev/null; for i in \$(seq 60); do kill -0 \$P 2>/dev/null || break; sleep 1; done; kill -0 \$P 2>/dev/null && { kill -9 \$P; echo SIGKILLED; }; pgrep -x llama-server >/dev/null && echo STILL_RUNNING || echo stopped; echo abort_lines \$(grep -E 'ggml_abort|GGML_ASSERT|SIGABRT|Aborted|out of memory|cudaMalloc failed' \$W/$CELL.log | wc -l)"
done
echo "######## CELLS DONE $(date -Is)"
