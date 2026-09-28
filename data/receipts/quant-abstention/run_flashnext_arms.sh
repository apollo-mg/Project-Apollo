#!/usr/bin/env bash
# PREREG_FLASHNEXT.md: arms FNQ2 -> FNIQ4 (smallest expert spill that loads) -> FNQ2X (Q2 at FNIQ4's spill).
# One fresh llama-server per arm on .194 (all four P100s), one discarded warm-up request, clocks + shard hashes in the
# arm's meta. Resumable: run_main.py skips ids already written, so a re-run only redoes the servers.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
Q2='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf'
IQ4='~/AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf'
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
mkdir -p "$HERE/raw/logs"; LOG="$HERE/raw/logs/flashnext_arms.log"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
# routed experts of the last k of the 48 layers on the CPU (the residency run's EXPS_44_47 at k=4)
exps() { local k=$1 l=""; for i in $(seq $((48 - k)) 47); do l="$l${l:+|}$i"; done; printf 'blk\\.(%s)\\.ffn_(up|down|gate)_exps=CPU' "$l"; }

stop_server() {
  ssh "$H" 'for f in ~/fn_server.pid ~/fn_feas.pid; do p=$(cat $f 2>/dev/null); [ -n "$p" ] || continue;
            kill $p 2>/dev/null; while kill -0 $p 2>/dev/null; do sleep 1; done; rm -f $f; done'
}

start_server() {   # start_server ARM MODEL [OT]  -> 0 when healthy, 1 when the server died (e.g. OOM)
  local arm=$1 model=$2 ot=${3:-}
  stop_server
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model $FLAGS ${ot:+-ot '$ot'} \
            > ~/fn_$arm.log 2>&1 < /dev/null & echo \$! > ~/fn_server.pid"
  for i in $(seq 1 120); do
    curl -sf -m 5 "$URL/health" >/dev/null && return 0
    ssh "$H" 'kill -0 $(cat ~/fn_server.pid) 2>/dev/null' || { log "$arm: server died: $(ssh "$H" "tail -3 ~/fn_$arm.log")"; return 1; }
    sleep 5
  done
  log "$arm: not healthy after 600 s"; return 1
}

run_arm() {        # run_arm ARM MODEL [OT]  (server already healthy)
  local arm=$1 model=$2 ot=${3:-}
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  local gpus shas
  gpus=$(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,clocks.sm,memory.used --format=csv,noheader' | tr '\n' ';')
  shas=$(ssh "$H" "grep '$(basename "$(dirname "$model")")/' ~/flashnext_sha256.txt" | awk '{print substr($1,1,16)}' | tr '\n' ',')
  local meta
  meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256_prefixes","build","flags","ot","gpus","host"], sys.argv[1:]))))' \
         "$arm" "$model" "$shas" "buun 0b2789f23 build_sm60" "$FLAGS" "$ot" "$gpus" ".194 4xP100")
  log "$arm: running M1 (ot='${ot:-none}')"
  $PY "$HERE/run_main.py" --url "$URL" --arm "$arm" --meta "$meta" --expect-variants "$VAR" >> "$LOG" 2>&1
  log "$arm: run_main exit $? ($(($(wc -l < "$HERE/raw/main_$arm.jsonl") - 1)) rows)"
}

log "== flashnext arms start"
start_server FNQ2 "$Q2" && run_arm FNQ2 "$Q2" || log "FNQ2 failed to start"
K=""
for k in 4 6 8 10 12; do
  log "FNIQ4: trying k=$k"
  if start_server FNIQ4 "$IQ4" "$(exps $k)"; then K=$k; break; fi
done
if [ -n "$K" ]; then
  echo "$K" > "$HERE/raw/logs/flashnext_iq4_k.txt"; log "FNIQ4: loads at k=$K"
  run_arm FNIQ4 "$IQ4" "$(exps $K)"
  start_server FNQ2X "$Q2" "$(exps $K)" && run_arm FNQ2X "$Q2" "$(exps $K)" || log "FNQ2X failed to start"
else
  log "FNIQ4: no k up to 12 loads -- Deviation needed"
fi
stop_server
log "== flashnext arms done"
