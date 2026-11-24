#!/bin/bash
# Added after the result (not preregistered): SNL replayed on the same build, card and flags as arm SNL2, so the PR head's
# 209 changed answers (E1) can be read against same-build run-to-run variation.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/sensenova-loop; QA=$R/data/receipts/quant-abstention
PY=$R/venv_cachyos/bin/python3; PORT=8095; FAITH=$R/engines/llama_cpp_4bc61eed/build_rocm/bin
SNLF=/mnt/TG_2TB/AI/Models/sensenova-loop-9b-gguf/SenseNova-Loop-9B-Q8_0.gguf
FLAGS="-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
S=$H/raw/state_replay.log; log() { echo "$* $(date '+%F %T')" >> $S; }
$FAITH/llama-server -m $SNLF $FLAGS --host 127.0.0.1 --port $PORT > $H/raw/server_SNL2.log 2>&1 &
SP=$!; ok=0; for i in $(seq 180); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && { ok=1; break; }; sleep 2; done
if [ $ok = 1 ]; then
  ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm SNL2 --max-tokens 1024 --usage \
      --meta "{\"model\": \"SenseNova-Loop-9B-Q8_0.gguf\", \"sha256\": \"0db6188d...\", \"commit\": \"4bc61eed7 (llama.cpp PR 32588)\", \"flags\": \"$FLAGS\", \"host\": \"RX 9070 XT\", \"note\": \"replay of SNL, added after the result\"}" > $H/raw/run_SNL2.log 2>&1 )
  log "SNL2 rc=$? rows=$(( $(wc -l < $QA/raw/main_SNL2.jsonl) - 1 ))"
else log "SNL2 server failed"; fi
kill $SP; wait $SP 2>/dev/null
log REPLAY_DONE
