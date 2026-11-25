#!/bin/bash
# PREREG_LOOP_DIAL arms on the desktop: SNL_L2R (replay; must match SNL 240/240), then SNL_L1, SNL_L3.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/sensenova-loop/loopcount; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state_m1.log; mkdir -p $H/raw; log() { echo "$* $(date '+%F %T')" >> $S; }
BIN=$R/engines/llama_cpp_4bc61eed/build_rocm/bin; D=/mnt/TG_2TB/AI/Models/sensenova-loop-9b-gguf; PORT=8095
FLAGS="-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
run() {  # run ARM FILE
  $R/tools/rocm724.sh $BIN/llama-server -m $2 $FLAGS --host 127.0.0.1 --port $PORT > $H/raw/server_$1.log 2>&1 &
  SP=$!; ok=0; for i in $(seq 120); do curl -s 127.0.0.1:$PORT/health | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  if [ $ok = 1 ]; then
    ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm $1 --max-tokens 1024 --usage \
        --meta "{\"model\": \"$(basename $2) ($(sha256sum < $2 | cut -c1-16))\", \"commit\": \"4bc61eed7 (llama.cpp PR 32588), ROCm 7.2.4 runtime via tools/rocm724.sh\", \"flags\": \"$FLAGS\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_LOOP_DIAL.md\"}" > $H/raw/run_$1.log 2>&1 )
    log "$1 rc=$? rows=$(( $(wc -l < $QA/raw/main_$1.jsonl) - 1 ))"
  else log "$1 server failed"; fi
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
}
run SNL_L2R $D/SenseNova-Loop-9B-Q8_0.gguf
SAME=$($PY -c "
import json
a = {r['id']: r for r in map(json.loads, open('$QA/raw/main_SNL.jsonl')) if 'id' in r}
b = {r['id']: r for r in map(json.loads, open('$QA/raw/main_SNL_L2R.jsonl')) if 'id' in r}
print(sum(a[i].get('content') == b.get(i, {}).get('content') for i in a))")
log "replay SNL_L2R vs SNL: $SAME of 240 identical"
[ "$SAME" = 240 ] || { log "STOP: the replay drifted"; exit 1; }
run SNL_L1 $D/loops/SenseNova-Loop-9B-Q8_0-loops1.gguf
run SNL_L3 $D/loops/SenseNova-Loop-9B-Q8_0-loops3.gguf
log DIAL_M1_DONE
