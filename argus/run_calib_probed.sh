#!/usr/bin/env bash
# Same as run_calib.sh but records server throughput before each pass. AFM-26: a degrading
# server produces timeouts that look like model failures, so the speed probe must be part of
# the run record rather than something reconstructed afterwards.
set -u
L="$1"; PORT="$2"; FR="$3"
A=/mnt/TG_2TB/Projects/Apollo/argus; PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd "$A"
# Hold the benchmark lock for the whole leg so the ledger (and anything else that polls a model
# endpoint) stays off the fleet. The trap releases it on normal exit AND on INT/TERM, so a
# killed run does not leave the lock behind -- though the lock is PID-checked anyway.
/mnt/TG_2TB/Projects/Apollo/tools/benchmark_lock.sh acquire "$L calibration"
trap '/mnt/TG_2TB/Projects/Apollo/tools/benchmark_lock.sh release' EXIT INT TERM
for i in $(seq 1 5); do
  T0=$(date +%s%N)
  curl -s -m 60 -o /tmp/probe.json -X POST http://127.0.0.1:8090/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"model":"o","messages":[{"role":"user","content":"Reply with one word: ok"}],"max_tokens":24}' 2>/dev/null
  T1=$(date +%s%N)
  TPS=$($PY -c "
import json
try:
  d=json.load(open('/tmp/probe.json')); ct=(d.get('usage') or {}).get('completion_tokens') or 0
  print(f'{ct/(($T1-$T0)/1e9):.1f}')
except Exception: print('0')")
  echo "######## $L pass $i/5  $(date -Iseconds)  server_tok_s=$TPS"
  timeout 9000 $PY driver.py --transport gateway --base http://127.0.0.1:$PORT \
      --fake-root "$FR" --scenarios runs/pool_no_thursday.json \
      --out runs/calib_$L.jsonl --events runs/live_$L.jsonl --timeout 600 2>&1 | tail -18
done
