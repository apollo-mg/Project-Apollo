#!/bin/bash
# PREREG_IDK_LORA2 chain on the RX 9070 XT: F2/F3 base answers -> LORA2 training -> conversion -> E1 (run_main) ->
# BASE byte-identity smoke -> E2 (BASE, LORA, LORA2) + normal-use prompts -> analysis (audit added by hand after).
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/idk-lora; G=/mnt/TG_2TB/models_small/gguf; A=/mnt/TG_2TB/models_small/idk_adapters
SRV=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server; PY=$R/venv_cachyos/bin/python3; M=$G/granite-4.1-3b-Q8_0.gguf
S=$H/raw/stageR2_state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
up() { for i in $(seq 120); do curl -s 127.0.0.1:$1/health 2>/dev/null | grep -q ok && return 0; sleep 2; done; return 1; }
F="-ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --host 127.0.0.1"
log "R2 start"
$SRV -m $M $F --port 8095 > $H/raw/server_r2_formats.log 2>&1 & SP=$!; up 8095
$PY $H/round2_gen.py formats http://127.0.0.1:8095 > $H/raw/r2_formats.log 2>&1; log "formats rc=$? rows=$(wc -l < $H/raw/formats_G41.jsonl)"
kill $SP; wait $SP 2>/dev/null
$PY $H/train_lora.py lora2 $A/lora2 > $H/raw/train_lora2.log 2>&1; rc=$?; log "train lora2 rc=$rc $(tail -1 $H/raw/train_lora2.log)"
[ $rc -ne 0 ] && { log "R2 STOP: training failed"; exit 1; }
$PY $R/engines/buun-llama-cpp/convert_lora_to_gguf.py $A/lora2/adapter --base /mnt/TG_2TB/models_small/granite-4.1-3b \
  --outtype f16 --outfile $A/lora2/adapter.gguf > $H/raw/convert_lora2.log 2>&1 || { log "R2 STOP: convert failed"; exit 1; }
$SRV -m $M $F --port 8095 --lora $A/lora2/adapter.gguf > $H/raw/server_r2_e1.log 2>&1 & SP=$!; up 8095
META="{\"model\": \"granite-4.1-3b-Q8_0.gguf + lora2 adapter ($(stat -c %s $A/lora2/adapter.gguf) B)\", \"build\": \"buun 38ada0e1b build_rocm\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_IDK_LORA2.md\"}"
( cd $R/data/receipts/quant-abstention && $PY run_main.py --url http://127.0.0.1:8095 --arm IDK_LORA2 --max-tokens 1024 --usage \
    --no-think-check --meta "$META" > $H/raw/run_IDK_LORA2.log 2>&1 ); log "E1 LORA2 rc=$?"
kill $SP; wait $SP 2>/dev/null
$SRV -m $M $F --port 8098 > $H/raw/server_r2_plain.log 2>&1 & SP1=$!
$SRV -m $M $F --port 8095 --lora $A/lora/adapter.gguf,$A/lora2/adapter.gguf --lora-init-without-apply > $H/raw/server_r2_two.log 2>&1 & SP2=$!
up 8098; up 8095
curl -s 127.0.0.1:8095/lora-adapters >> $S; echo >> $S
if $PY $H/round2_gen.py smoke http://127.0.0.1:8098 http://127.0.0.1:8095 >> $S 2>&1; then
  kill $SP1; wait $SP1 2>/dev/null
  $PY $H/round2_gen.py e2 http://127.0.0.1:8095 > $H/raw/r2_e2.log 2>&1; log "E2 rc=$?"
else
  log "R2 STOP: BASE through the two-adapter server differs from a plain server"; kill $SP1
fi
kill $SP2; wait $SP2 2>/dev/null
$PY $H/analyze_idk2.py > $H/raw/analyze2.log 2>&1; log "analyze2 rc=$?"
log R2_DONE
