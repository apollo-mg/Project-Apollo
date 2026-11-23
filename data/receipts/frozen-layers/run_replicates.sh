#!/bin/bash
# PREREG_FROZEN_LAYERS Amendment 1: the four adapted arms at training seeds 1 and 2 (FZ_<ARM>_S1, _S2; train -> convert
# -> layer check -> serve with --lora -> M1). FZ_BASE is shared with the main run. One GPU job at a time on the RX 9070 XT; servers stopped by their recorded PID.
# Server flags as the October IDK arms plus --cache-ram 0 (host RAM; the same for every arm in this sitting).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/frozen-layers; I=$R/data/receipts/idk-lora
G=/mnt/TG_2TB/models_small/gguf; A=/mnt/TG_2TB/models_small/idk_adapters
SRV=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server; PY=$R/venv_cachyos/bin/python3; PORT=8095
S=$H/raw/state_replicate.log; log() { echo "$* $(date '+%F %T')" >> $S; }
serve() {  # serve EXTRA_ARGS... ; sets SP
  $SRV -m $G/granite-4.1-3b-Q8_0.gguf "$@" -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --cache-ram 0 \
    --host 127.0.0.1 --port $PORT > $H/raw/server_$TAG.log 2>&1 &
  SP=$!; echo $SP > $H/raw/server.pid
  for i in $(seq 120); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && return 0; sleep 2; done; return 1
}
m1() {  # m1 ARM META
  ( cd $R/data/receipts/quant-abstention && $PY run_main.py --url http://127.0.0.1:$PORT --arm $1 --max-tokens 1024 \
      --usage --no-think-check --meta "$2" > $H/raw/run_$1.log 2>&1 )
  log "$1 rc=$? rows=$(( $(cat $R/data/receipts/quant-abstention/raw/main_$1.jsonl 2>/dev/null | wc -l) - 1 ))"
}
BUILD="buun $(git -C $R/engines/buun-llama-cpp rev-parse --short=9 HEAD) build_rocm"
log "start $BUILD"
for SEEDN in 1 2; do for spec in ALL:0-39 FRZ10:0-29 FRZ20:0-19 LAST20:20-39; do
  NAME=${spec%%:*}; LY=${spec#*:}; ARM=FZ_${NAME}_S$SEEDN; D=$A/fz_$(echo $NAME | tr A-Z a-z)_s$SEEDN
  [ -e $D ] && gio trash $D
  TRAIN_SEED=$SEEDN LORA_LAYERS=$LY $PY $I/train_lora.py ctrl $D > $H/raw/train_$ARM.log 2>&1; rc=$?
  log "train $ARM layers $LY rc=$rc $(tail -1 $H/raw/train_$ARM.log)"
  [ $rc -ne 0 ] && { log "$ARM not run: training failed"; continue; }
  cp $D/train_log.json $H/raw/train_log_$ARM.json
  $PY $R/engines/buun-llama-cpp/convert_lora_to_gguf.py $D/adapter --base /mnt/TG_2TB/models_small/granite-4.1-3b \
    --outtype f16 --outfile $D/adapter.gguf > $H/raw/convert_$ARM.log 2>&1 || { log "$ARM not run: convert failed"; continue; }
  $PY $H/check_adapter.py $D/adapter.gguf $LY >> $S 2>&1 || { log "$ARM VOID: layer check failed"; continue; }
  echo "$(sha256sum < $D/adapter.gguf | cut -c1-64)  $ARM adapter.gguf" >> $H/raw/adapter_sha256.txt
  TAG=$NAME; if serve --lora $D/adapter.gguf; then
    m1 $ARM "{\"model\": \"granite-4.1-3b-Q8_0.gguf + ctrl adapter on layers $LY, train seed $SEEDN ($(stat -c %s $D/adapter.gguf) B)\", \"build\": \"$BUILD\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_FROZEN_LAYERS.md\"}"
  else log "$ARM server failed"; fi
  kill $SP; wait $SP 2>/dev/null
done; done
log REPLICATE_DONE
