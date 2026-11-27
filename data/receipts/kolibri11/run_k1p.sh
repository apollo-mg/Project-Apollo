#!/bin/bash
# EXPLORATORY (after the registered KOL11/KOL1 results): KOL1P = the same Kolibri 1 file on the PR #32891 build (Aleph
# Alpha's kolibri1 implementation) with the two overrides it needs, to see whether KOL1's numbers depend on October's port.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/kolibri11; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.194; IP=10.0.0.194; PORT=8096; BIN='~/llama.cpp-pr32891/build_sm60/bin'
FLAGS="-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0 --override-kv tokenizer.ggml.pre=str:qwen2 --override-kv kolibri1.expert_gating_func=int:2"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
rx "GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN/llama-server -m ~/AI/Models/kolibri/Kolibri-1-Q4_K_M.gguf $FLAGS --host 0.0.0.0 --port $PORT > ~/k11_server_KOL1P.log 2>&1 < /dev/null & echo \$! > ~/k11_server.pid"
ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "KOL1P server healthy=$ok"
if [ $ok = 1 ]; then
  ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm KOL1P --usage --timeout 900 \
      --meta "{\"model\": \"Kolibri-1-Q4_K_M.gguf\", \"commit\": \"PR 32891 5f4d22289 (exploratory)\", \"flags\": \"$FLAGS\", \"host\": \".194 4x P100\", \"prereg\": \"none: exploratory, after PREREG_KOLIBRI11 results\"}" > $H/raw/run_KOL1P.log 2>&1 )
  log "KOL1P rc=$? rows=$(( $(wc -l < $QA/raw/main_KOL1P.jsonl) - 1 ))"
fi
rx "kill \$(cat ~/k11_server.pid) 2>/dev/null"; sleep 8
log K1P_DONE
