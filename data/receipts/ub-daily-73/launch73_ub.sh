#!/bin/bash
# PREREG_UB_DAILY_73.md. Runs ON .73 (copied to ~/ub73_launch.sh): start one cell's llama-server detached, record its
# exact command, live clocks before the leg, and a 2 s power/clock/memory log during it. ./launch73_ub.sh CELL
set -u
CELL=$1; W=~/ub73; mkdir -p "$W"
MODEL='/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf'
MMPROJ='/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf'
BIN_D=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server   # buun 510cbbbfa + f08683ffa (daily)
NET=(--host 0.0.0.0 --port 8080)
# The wake proxy's WP_START_CMD minus --resume* -- byte-identical to kmic-p100-73's D1/D2 legs
DS=(-m "$MODEL" --mmproj "$MMPROJ" -ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 -fit off
    -sm tensor -fa on --spec-type draft-mtp --draft-max 3 --jinja --kv-unified
    --chat-template-kwargs '{"reasoning_effort":"medium"}' --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0
    --presence-penalty 0.0)
case $CELL in
  U512)  CMD=("$BIN_D" "${DS[@]}");;              # the daily command as served: no -ub, default 512
  U1024) CMD=("$BIN_D" "${DS[@]}" -ub 1024);;
  U2048) CMD=("$BIN_D" "${DS[@]}" -ub 2048);;
  *) echo "unknown cell $CELL"; exit 2;;
esac
pgrep -x llama-server >/dev/null && { echo "ABORT: a llama-server is already running"; exit 2; }
nvidia-smi --query-gpu=index,clocks.applications.graphics,clocks.sm,power.limit,temperature.gpu,memory.used \
  --format=csv,noheader > "$W/$CELL.clocks"
printf '%q ' "${CMD[@]}" "${NET[@]}" > "$W/$CELL.cmd"; echo >> "$W/$CELL.cmd"
setsid nohup "${CMD[@]}" "${NET[@]}" > "$W/$CELL.log" 2>&1 < /dev/null &
echo $! > "$W/$CELL.pid"
setsid nohup nvidia-smi --query-gpu=timestamp,index,power.draw,clocks.sm,temperature.gpu,memory.used \
  --format=csv,noheader,nounits -lms 2000 > "$W/$CELL.power" 2>&1 < /dev/null &
echo $! > "$W/$CELL.smipid"
echo "started $CELL pid $(cat "$W/$CELL.pid")"
