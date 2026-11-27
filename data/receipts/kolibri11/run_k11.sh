#!/bin/bash
# PREREG_KOLIBRI11: KOL11 (Kolibri 1.1 Q4_K_M, official) on llama.cpp PR #32891 5f4d22289 build_sm60, then KOL1 (Kolibri 1
# Q4_K_M, Hob-forge, the October file) on October's port 1 (Hob-forge 60d1d51cc build_sm60, validated against an
# independent port in RESULT_KOLIBRI_194). .194 (4x P100); M1 driven from the desktop, thinking off, run_main defaults
# (1,024 tokens, slot readout on) plus --usage.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/kolibri11; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.194; IP=10.0.0.194; PORT=8096; MD='~/AI/Models/kolibri'
FLAGS="-ngl 99 -sm layer -fa on -fit off -c 8192 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
for spec in "KOL11|Kolibri-1.1-Q4_K_M.gguf|~/llama.cpp-pr32891/build_sm60/bin|PR 32891 5f4d22289" "KOL1|Kolibri-1-Q4_K_M.gguf|~/k194/llama.cpp/build_sm60/bin|Hob-forge port 1 60d1d51cc"; do
  IFS='|' read -r ARM FILE BIN COMMIT <<< "$spec"
  P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"
  for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
  log "$ARM: VRAM before load (max) ${u} MiB; binary $(rx "sha256sum $BIN/llama-server | cut -c1-16"); model $(rx "sha256sum $MD/$FILE | cut -c1-16"); clocks $(rx "nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,power.limit --format=csv,noheader | tr '\n' ' '")"
  rx "GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN/llama-server -m $MD/$FILE $FLAGS --host 0.0.0.0 --port $PORT > ~/k11_server_$ARM.log 2>&1 < /dev/null & echo \$! > ~/k11_server.pid"
  ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "$ARM server healthy=$ok"
  if [ $ok = 1 ]; then
    ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm $ARM --usage --timeout 900 \
        --meta "{\"model\": \"$FILE\", \"commit\": \"$COMMIT\", \"flags\": \"$FLAGS\", \"host\": \".194 4x P100\", \"prereg\": \"PREREG_KOLIBRI11.md\"}" > $H/raw/run_$ARM.log 2>&1 )
    log "$ARM rc=$? rows=$(( $(wc -l < $QA/raw/main_$ARM.jsonl) - 1 ))"
  fi
  rx "kill \$(cat ~/k11_server.pid) 2>/dev/null"; sleep 8; scp -q "$HOST:k11_server_$ARM.log" $H/raw/
done
log K11_DONE
