#!/bin/bash
# PREREG_IDK_LORA Stage B, in order, after the pool labels exist: BIAS fit (offline) and M1 run; IBM's adapter on calib
# and M1; LORA and CTRL training (stops at the 300-item rule), adapter conversion, M1 runs with --lora; analysis.
# One GPU job at a time on the RX 9070 XT; servers stopped by their recorded PID.
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/idk-lora; G=/mnt/TG_2TB/models_small/gguf; A=/mnt/TG_2TB/models_small/idk_adapters
SRV=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server; PY=$R/venv_cachyos/bin/python3; PORT=8095
S=$H/raw/stageB_state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
serve() {  # serve EXTRA_ARGS... ; sets SP
  $SRV -m $G/granite-4.1-3b-Q8_0.gguf "$@" -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --host 127.0.0.1 --port $PORT > $H/raw/server_$TAG.log 2>&1 &
  SP=$!; echo $SP > $H/raw/server.pid
  for i in $(seq 120); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && return 0; sleep 2; done; return 1
}
until grep -q LABEL_DONE $H/raw/stageA_state.log 2>/dev/null; do sleep 15; done
mkdir -p $A
log "stageB start"
$PY $H/bias_arm.py fit >> $S 2>&1; log "bias fit rc=$?"
TAG=bias; serve && { $PY $H/bias_arm.py run http://127.0.0.1:$PORT > $H/raw/run_IDK_BIAS.log 2>&1; log "bias run rc=$? rows=$(wc -l < $H/raw/IDK_BIAS.jsonl)"; }; kill $SP; wait $SP 2>/dev/null
$PY $H/ibm_arm.py > $H/raw/run_IDK_IBM.log 2>&1; log "ibm rc=$? $(tail -1 $H/raw/run_IDK_IBM.log)"
for MODE in lora ctrl; do
  ARM=IDK_$(echo $MODE | tr a-z A-Z)
  $PY $H/train_lora.py $MODE $A/$MODE > $H/raw/train_$MODE.log 2>&1; rc=$?; log "train $MODE rc=$rc $(tail -1 $H/raw/train_$MODE.log)"
  [ $rc -ne 0 ] && { log "train $MODE failed or stop rule: $ARM not run"; continue; }
  $PY $R/engines/buun-llama-cpp/convert_lora_to_gguf.py $A/$MODE/adapter --base /mnt/TG_2TB/models_small/granite-4.1-3b \
    --outtype f16 --outfile $A/$MODE/adapter.gguf > $H/raw/convert_$MODE.log 2>&1 || { log "convert $MODE failed"; continue; }
  TAG=$MODE; serve --lora $A/$MODE/adapter.gguf || { log "$ARM server failed"; kill $SP; continue; }
  META="{\"model\": \"granite-4.1-3b-Q8_0.gguf + $MODE adapter ($(stat -c %s $A/$MODE/adapter.gguf) B)\", \"build\": \"buun 38ada0e1b build_rocm\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_IDK_LORA.md\"}"
  ( cd $R/data/receipts/quant-abstention && $PY run_main.py --url http://127.0.0.1:$PORT --arm $ARM --max-tokens 1024 --usage \
      --no-think-check --meta "$META" > $H/raw/run_$ARM.log 2>&1 )
  log "$ARM rc=$? rows=$(( $(cat $R/data/receipts/quant-abstention/raw/main_$ARM.jsonl 2>/dev/null | wc -l) - 1 ))"
  kill $SP; wait $SP 2>/dev/null
done
$PY $H/analyze_idk.py > $H/raw/analyze.log 2>&1; log "analyze rc=$?"
log STAGEB_DONE
