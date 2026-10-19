#!/bin/bash
# QW27 arms of PREREG_SESSION_STATE.md: Qwen3.8-27B (the .73 daily) through the wake proxy, twice (the daily is
# bistable). Holds the benchmark lock so the hourly ledger does not interleave its own requests on .73.
set -u
R=/mnt/TG_2TB/Projects/Apollo; PY=$R/venv_cachyos/bin/python3; E=$HOME/.local/share/apollo/session_state_eval
H=http://127.0.0.1:8099; TK='{"enable_thinking": false}'
log () { echo "$(date +%T) $*" >> $E/chain_qw.log; }
$R/tools/benchmark_lock.sh acquire "session-state QW27 arms" >> $E/chain_qw.log 2>&1
trap '$R/tools/benchmark_lock.sh release >> $E/chain_qw.log 2>&1' EXIT
log "start"
for RUN in QW27a QW27b; do
  $PY $R/tools/session_state_eval.py arm-writer --name $RUN --host $H --template-kwargs "$TK" >> $E/chain_qw.log 2>&1 || { log "ABORT: $RUN failed"; exit 1; }
  log "$RUN done"
done
log "DONE"
