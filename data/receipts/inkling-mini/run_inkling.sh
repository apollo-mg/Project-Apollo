#!/bin/bash
# PREREG_INKLING_MINI: arm INK on .73 (both P100s, -ts 1,3), M1 driven from the desktop. Pauses the wake proxy, restores it.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-mini; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; BIN='~/llama.cpp-33aeb17f/build_sm60/bin'; M=/mnt/models/inkling/Inkling-2-Mini-AD-Q6_K.gguf
FLAGS="-ngl 99 -sm layer -fit off -ts 1,3 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 5
systemctl --user stop apollo-wake-proxy; log "wake proxy stopped"
rx "setsid nohup sleep 14400 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.inkling"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
log "VRAM used before load (max of the two) ${u} MiB; binary $(rx "sha256sum $BIN/llama-server | cut -c1-16"); model $(rx "sha256sum $M | cut -c1-16")"
rx "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN/llama-server -m $M $FLAGS --host 0.0.0.0 --port $PORT > ~/inkling/server_INK.log 2>&1 < /dev/null & echo \$! > ~/inkling/server.pid"
ok=0; for i in $(seq 300); do curl -s -m 3 $IP:$PORT/health | grep -q ok && { ok=1; break; }; sleep 2; done; log "server healthy=$ok"
if [ $ok = 1 ]; then
  ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm INK --max-tokens 4096 --timeout 900 --usage --skip-slot --no-think-check \
      --template-kwargs '{"reasoning_effort": "none"}' \
      --meta "{\"model\": \"Inkling-2-Mini-AD-Q6_K.gguf (AtomicChat, aebacd90...)\", \"commit\": \"33aeb17f8\", \"flags\": \"$FLAGS\", \"host\": \".73 2x P100\", \"prereg\": \"PREREG_INKLING_MINI.md\"}" > $H/raw/run_INK.log 2>&1 )
  log "INK rc=$? rows=$(( $(wc -l < $QA/raw/main_INK.jsonl) - 1 ))"
fi
rx "kill \$(cat ~/inkling/server.pid) 2>/dev/null"; sleep 5; scp -q "$HOST:inkling/server_INK.log" $H/raw/
rx "kill \$(cat /tmp/apollo-busy.inkling) 2>/dev/null; rm -f /tmp/apollo-busy.inkling"
systemctl --user start apollo-wake-proxy; log "wake proxy started; INK_DONE"
