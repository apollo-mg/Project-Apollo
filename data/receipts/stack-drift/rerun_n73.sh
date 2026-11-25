#!/bin/bash
# Re-launch the two .73 runs whose servers never came up on 11-24 (no rows): DR_N73_1 (cudaMalloc OOM -- the daily
# server, killed a moment before, had not released its VRAM) and DR27_N73 (the 28 GB file on .73's HDD did not load within
# the 8-minute window). Same binary, files, flags and arms; waits for free VRAM; 40 minutes for the 27B to load.
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state_drift_n73.log; log() { echo "$* $(date '+%F %T')" >> $S; }
HOST=mark@10.0.0.73; IP=10.0.0.73; PORT=8190; BIN='~/llama.cpp-33aeb17f/build_sm60/bin'; WD='~/drift'
FL="-c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
rx() { ssh -o BatchMode=yes $HOST "$1"; }
curl -s -m 120 -X POST 127.0.0.1:8099/wake > /dev/null; sleep 5
systemctl --user stop apollo-wake-proxy; log "rerun: wake proxy stopped"
rx "setsid nohup sleep 21600 > /dev/null 2>&1 < /dev/null & echo \$! > /tmp/apollo-busy.drift"
P=$(rx 'pgrep -x llama-server'); [ -n "$P" ] && rx "kill $P"; log "rerun: daily server pids stopped: ${P:-none}"
for i in $(seq 60); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 5; done
log "rerun: VRAM used (max of the two cards) ${u} MiB"
serve() {  # serve TAG MODEL ENV TRIES
  rx "$3 setsid nohup $BIN/llama-server -m $2 -ngl 99 -sm layer -fit off $FL --host 0.0.0.0 --port $PORT > $WD/server_$1.log 2>&1 < /dev/null & echo \$! > $WD/server.pid"
  for i in $(seq $4); do curl -s -m 3 $IP:$PORT/health 2>/dev/null | grep -q ok && return 0; sleep 2; done; return 1
}
stop() { rx "kill \$(cat $WD/server.pid) 2>/dev/null"; for i in $(seq 30); do u=$(rx "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1"); [ "${u:-99999}" -lt 500 ] && break; sleep 2; done; }
m1() { ( cd $QA && $PY run_main.py --url http://$IP:$PORT --arm $1 --max-tokens 1024 --usage \
      --meta "{\"model\": \"$2\", \"commit\": \"33aeb17f8\", \"stack\": \"n73\", \"prereg\": \"PREREG_STACK_DRIFT.md\", \"note\": \"re-launch after a failed server start\"}" > $H/raw/run_$1.log 2>&1 ); log "$1 rc=$? rows=$(( $(wc -l < $QA/raw/main_$1.jsonl) - 1 ))"; }
if serve DR_N73_1 /mnt/models/drift/Qwen3.5-9B-Q8_0.gguf "CUDA_VISIBLE_DEVICES=0 GGML_CUDA_ALLREDUCE=internal" 240; then m1 DR_N73_1 "Qwen3.5-9B-Q8_0.gguf (f904644b)"; else log "rerun: DR_N73_1 server failed again"; fi; stop
if serve DR27_N73 /mnt/HDD/kld/Qwen3.8-27B-Q8_0.gguf "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal" 1200; then m1 DR27_N73 "Qwen3.8-27B-Q8_0.gguf (a680f44a)"; else log "rerun: DR27_N73 server failed again"; fi; stop
scp -q "$HOST:$WD/server_DR*_N73*.log" $H/raw/ 2>/dev/null
rx "kill \$(cat /tmp/apollo-busy.drift) 2>/dev/null; rm -f /tmp/apollo-busy.drift"
systemctl --user start apollo-wake-proxy; log "rerun: wake proxy started; RERUN_DONE"
