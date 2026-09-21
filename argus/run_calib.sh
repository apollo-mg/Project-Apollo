#!/usr/bin/env bash
# Calibrate the v1 pool. ARG1=label ARG2=gateway-port ARG3=fake-root
# Timeout now enforced by a WALL-CLOCK deadline inside chat_stream -- urllib's timeout is
# per-socket-op and a trickling SSE stream never tripped it (one scenario ran 6827s under a
# nominal 1200s cap and ate a whole 2h pass).
set -u
L="$1"; PORT="$2"; FR="$3"
A=/mnt/TG_2TB/Projects/Apollo/argus
PY=/mnt/TG_2TB/AI/hermes-go/.venv/bin/python
cd "$A"
# Hold the benchmark lock for the whole leg so the ledger (and anything else that polls a model
# endpoint) stays off the fleet. The trap releases it on normal exit AND on INT/TERM, so a
# killed run does not leave the lock behind -- though the lock is PID-checked anyway.
/mnt/TG_2TB/Projects/Apollo/tools/benchmark_lock.sh acquire "$L calibration"
trap '/mnt/TG_2TB/Projects/Apollo/tools/benchmark_lock.sh release' EXIT INT TERM
for i in $(seq 1 5); do
  echo "######## $L pass $i/5  $(date -Iseconds)"
  timeout 9000 $PY driver.py --transport gateway --base http://127.0.0.1:$PORT \
      --fake-root "$FR" --scenarios scenarios_v1_pool.json \
      --out runs/calib_$L.jsonl --events runs/live_$L.jsonl --timeout 600 2>&1 | tail -18
done
echo "######## $L calibration done $(date -Iseconds)"
