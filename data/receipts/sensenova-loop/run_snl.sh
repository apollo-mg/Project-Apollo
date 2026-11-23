#!/bin/bash
# PREREG_SENSENOVA_LOOP run on the RX 9070 XT: wait for the verified download and the 4bc61eed7 build; G1 load check;
# G2 perplexity gate (SNL vs Q35R on the same build); then M1 arms Q35R, SNL (4bc61eed7) and SNLH (PR head 0ba8e4adf).
# One GPU job at a time; servers stopped by their recorded PID; the run stops at a failed gate.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/sensenova-loop; QA=$R/data/receipts/quant-abstention
PY=$R/venv_cachyos/bin/python3; PORT=8095
FAITH=$R/engines/llama_cpp_4bc61eed/build_rocm/bin; HEADB=$R/engines/llama_cpp_0ba8e4ad/build_rocm/bin
SNLF=/mnt/TG_2TB/AI/Models/sensenova-loop-9b-gguf/SenseNova-Loop-9B-Q8_0.gguf; SNLSHA=0db6188dbba93527cfd8e162ad6f8331593025d9f9b9e9a3e846a5faa601a0d1
Q35=/mnt/TG_2TB/AI/Models/sci-distill-gguf/Qwen3.5-9B-Q8_0.gguf
WIKI=/mnt/TG_2TB/AI/kld/wikitext-2-raw/wiki.test.raw
FLAGS="-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
mkdir -p $H/raw; S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
serve() {  # serve BIN MODEL TAG ; sets SP
  $1/llama-server -m $2 $FLAGS --host 127.0.0.1 --port $PORT > $H/raw/server_$3.log 2>&1 &
  SP=$!; echo $SP > $H/raw/server.pid
  for i in $(seq 180); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && return 0; kill -0 $SP 2>/dev/null || return 1; sleep 2; done; return 1
}
m1() {  # m1 ARM META
  ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm $1 --max-tokens 1024 --usage --meta "$2" > $H/raw/run_$1.log 2>&1 )
  log "$1 rc=$? rows=$(( $(cat $QA/raw/main_$1.jsonl 2>/dev/null | wc -l) - 1 ))"
}
log "waiting for the download and the build"
until [ -s /mnt/TG_2TB/AI/Models/sensenova-loop-9b-gguf/sha256.txt ] && grep -q BUILD_OK $R/run/build_4bc61eed.log 2>/dev/null; do
  grep -q ABORT $R/run/build_4bc61eed.log 2>/dev/null && { log "STOP: 4bc61eed build aborted"; exit 1; }
  sleep 30
done
[ "$(cut -c1-64 /mnt/TG_2TB/AI/Models/sensenova-loop-9b-gguf/sha256.txt)" = "$SNLSHA" ] || { log "STOP: SNL sha256 mismatch"; exit 1; }
log "download verified; $(grep BUILD_OK $R/run/build_4bc61eed.log | cut -c1-60)"
# G1: load
if serve $FAITH $SNLF snl_g1; then
  A=$(grep -m1 -E "arch +=" $H/raw/server_snl_g1.log); L=$(grep -m1 -E "n_layer +=" $H/raw/server_snl_g1.log)
  log "G1 $A | $L | $(grep -m3 -i -E 'loop' $H/raw/server_snl_g1.log | tr '\n' ' ' | cut -c1-300)"
  kill $SP; wait $SP 2>/dev/null
  echo "$A" | grep -q sensenova_loop && echo "$L" | grep -q -E "= 57$" || { log "STOP: G1 failed"; exit 1; }
else log "STOP: G1 server failed to start"; kill $SP 2>/dev/null; exit 1; fi
# G2: perplexity, both models on the SNL build
for spec in Q35R:$Q35 SNL:$SNLF; do
  T=${spec%%:*}; M=${spec#*:}
  $FAITH/llama-perplexity -m $M -f $WIKI -c 512 --chunks 100 -ngl 99 -ctk f16 -ctv f16 > $H/raw/ppl_$T.log 2>&1
  log "ppl $T rc=$? $(grep -o 'Final estimate: PPL = [0-9.]*' $H/raw/ppl_$T.log)"
done
PQ=$(grep -o 'PPL = [0-9.]*' $H/raw/ppl_Q35R.log | tail -1 | cut -d' ' -f3); PS=$(grep -o 'PPL = [0-9.]*' $H/raw/ppl_SNL.log | tail -1 | cut -d' ' -f3)
python3 -c "import sys; q,s=float('$PQ' or 'nan'),float('$PS' or 'nan'); sys.exit(0 if s <= 1.5*q else 1)" \
  && log "G2 pass: SNL $PS vs Q35R $PQ" || { log "STOP: G2 failed: SNL $PS vs Q35R $PQ"; exit 1; }
# M1 arms
C4=$(git -C $R/engines/llama_cpp_4bc61eed rev-parse --short=9 HEAD); CH=$(git -C $R/engines/llama_cpp_0ba8e4ad rev-parse --short=9 HEAD)
for spec in Q35R:$FAITH:$Q35:$C4:f904644b SNL:$FAITH:$SNLF:$C4:0db6188d SNLH:$HEADB:$SNLF:$CH:0db6188d; do
  IFS=: read -r ARM BIN M C SHA <<< "$spec"
  if serve $BIN $M $ARM; then
    m1 $ARM "{\"model\": \"$(basename $M)\", \"sha256\": \"$SHA...\", \"commit\": \"$C (llama.cpp PR 32588)\", \"flags\": \"$FLAGS\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_SENSENOVA_LOOP.md\"}"
  else log "$ARM server failed"; fi
  kill $SP; wait $SP 2>/dev/null
done
log SNL_DONE
