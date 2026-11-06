#!/usr/bin/env bash
# PREREG_RIPPLE.md: arm RIP (Ripple-65B-Preview Q6_K, our conversion) on M1, one fresh server on all four P100s of .194.
# Waits for convert_and_stage.sh's STAGED line, checks the hash on .194 against it, starts and verifies the server, runs
# M1, stops the server, powers .194 off. Runs on the desktop. Resumable (run_main.py skips ids written).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/llama.cpp-67107ac/build_sm60/bin/llama-server'; F='~/AI/Models/ripple/Ripple-65B-Preview-Q6_K.gguf'
FLAGS="-ngl 99 -sm layer -c 10240 -ctk f16 -ctv f16 -np 1 -fit off --cache-ram 0 -lv 4 --host 0.0.0.0 --port $PORT"
STAGE=/mnt/TG_2TB/AI/Models/ripple-65b-gguf/stage.log; LOG="$QA/raw/logs/ripple.log"; mkdir -p "$QA/raw/logs"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

while [ "$(systemctl --user show ripple-stage2 -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
want=$(tail -1 "$STAGE" | sed -n 's/.*STAGED \([0-9a-f]\{64\}\)$/\1/p')
[ -n "$want" ] || { log "staging did not finish: $(tail -1 "$STAGE")"; exit 1; }
got=$(ssh "$H" "sha256sum $F" | cut -d' ' -f1); [ "$got" = "$want" ] || { log "HASH MISMATCH on .194: $got"; exit 1; }
log "file verified $want"
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "a llama-server is already running on .194 -- aborting"; exit 1; }
ssh "$H" "GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $F $FLAGS > ~/ripple_RIP.log 2>&1 < /dev/null &"
up=0; for i in $(seq 1 200); do sleep 5; curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "server died: $(ssh "$H" 'tail -3 ~/ripple_RIP.log')"; exit 1; }; done
[ $up = 1 ] || { log "not healthy after 1000 s"; exit 1; }
mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
[ "$(basename "$mp")" = Ripple-65B-Preview-Q6_K.gguf ] || { log "WRONG SERVER answered: $mp"; exit 1; }
ssh "$H" "grep -q 'K (f16).*V (f16)' ~/ripple_RIP.log" || { log "f16 KV line not found"; exit 1; }
mem=$(ssh "$H" 'nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits' | tr '\n' ' ')
for m in $mem; do [ "$m" -ge 8000 ] || { log "a GPU holds only $m MiB: $mem"; exit 1; }; done
gpus=$(ssh "$H" 'nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,memory.used --format=csv,noheader' | tr '\n' ';')
log "verified -- serving $(basename "$mp"); GPUs $gpus"
meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","build","flags","gpus","host"], sys.argv[1:]))))' \
  RIP "$F" "$want" "llama.cpp 67107ac34f build_sm60" "$FLAGS" "$gpus" ".194 4xP100")
$PY "$QA/run_main.py" --url "$URL" --arm RIP --meta "$meta" --max-tokens 8192 --skip-slot --no-think-check --usage \
  --timeout 7200 --neutral-penalties > "$QA/raw/logs/ripple_run.log" 2>&1
log "run_main exit $? ($(( $(wc -l < "$QA/raw/main_RIP.jsonl") - 1 )) rows)"
ssh "$H" 'pkill -x llama-server'
log "== done; powering .194 off"
"$ROOT/tools/s194.sh" off >> "$LOG" 2>&1
