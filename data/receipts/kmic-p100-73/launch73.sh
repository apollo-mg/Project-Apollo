#!/bin/bash
# PREREG_KMIC_VS_DAILY_73.md. Runs ON .73 (copied to ~/kmic73_launch.sh): start one cell's llama-server detached,
# record its exact command, live clocks before the leg, and a 2 s power/clock log during it. ./launch73.sh CELL
set -u
CELL=$1; W=~/kmic73; mkdir -p "$W"
MODEL='/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf'
MMPROJ='/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf'
BIN_D=/mnt/HDD/buun-510cb-nohost/build_sm60/bin/llama-server   # buun 510cbbbfa + f08683ffa (daily)
BIN_K=/mnt/HDD/kmic-p100/src/build-opt/bin/llama-server        # Kmic-68 e48e240a8
NET=(--host 0.0.0.0 --port 8080)
# M1: identical flags on both builds
MICRO=(-m "$MODEL" -ngl 99 -sm tensor -fa on -ctk f16 -ctv f16 -c 8192 -np 1 -b 2048 -ub 2048 -fit off)
# M2 D: the wake proxy's WP_START_CMD minus --resume*
DS=(-m "$MODEL" --mmproj "$MMPROJ" -ngl 99 -c 262144 -ctk vbr -ctv vbr --vbr-floor t4 --vbr-vram auto -np 2 -fit off
    -sm tensor -fa on --spec-type draft-mtp --draft-max 3 --jinja --kv-unified
    --chat-template-kwargs '{"reasoning_effort":"medium"}' --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0
    --presence-penalty 0.0)
# M2 K: Kaden's QUICKSTART.md command, plus our F16 projector, minus GGML_CUDA_P2P=1 (Deviation 3). KUB is the registered -ub fallback.
KS=(-m "$MODEL" -ngl 99 -sm tensor -fa 1 -ctk q4_0 -ctv q4_0 -c 262144 -b 32768 -ub "${KUB:-2048}" -np 1
    --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.2 -ngld 99 -ubd 64 -ctkd q4_0 -ctvd q4_0
    --jinja --temp 1.0 --top-k 20 --top-p 0.95 --min-p 0.0 --mmproj "$MMPROJ")
KENV=(GGML_CUDA_GRAPHS_PRE_VOLTA=3 LLAMA_SPEC_SAMPLE_TEMP=1.0 LLAMA_SPEC_DRAFT_TOPK=20)
case $CELL in
  MD1|MD2) CMD=(env GGML_CUDA_P2P=1 "$BIN_D" "${MICRO[@]}");;
  MD0|MD0a|MD0b) CMD=("$BIN_D" "${MICRO[@]}");;
  MK0|MK0a|MK0b) CMD=("$BIN_K" "${MICRO[@]}");;
  MK1|MK2) CMD=(env GGML_CUDA_P2P=1 "$BIN_K" "${MICRO[@]}");;
  D1|D2)   CMD=("$BIN_D" "${DS[@]}");;
  K1|K2)   CMD=(env "${KENV[@]}" "$BIN_K" "${KS[@]}");;
  *) echo "unknown cell $CELL"; exit 2;;
esac
pgrep -x llama-server >/dev/null && { echo "ABORT: a llama-server is already running"; exit 2; }
nvidia-smi --query-gpu=index,clocks.applications.graphics,clocks.sm,power.limit,temperature.gpu \
  --format=csv,noheader > "$W/$CELL.clocks"
printf '%q ' "${CMD[@]}" "${NET[@]}" > "$W/$CELL.cmd"; echo >> "$W/$CELL.cmd"
setsid nohup "${CMD[@]}" "${NET[@]}" > "$W/$CELL.log" 2>&1 < /dev/null &
echo $! > "$W/$CELL.pid"
setsid nohup nvidia-smi --query-gpu=timestamp,index,power.draw,clocks.sm,temperature.gpu --format=csv,noheader \
  -lms 2000 > "$W/$CELL.power" 2>&1 < /dev/null &
echo $! > "$W/$CELL.smipid"
echo "started $CELL pid $(cat "$W/$CELL.pid")"
