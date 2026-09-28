#!/usr/bin/env bash
# PREREG_FLASHNEXT_STOPPING.md: Flash-Next Q2 (-ngl 99) then IQ4 (-ngl 44) on the 16 CAL items at xhigh, card
# sampling, seeds 1001-1003, through run_fixture_structfix.py: the harness, flags and 16k context of the 27B Q6_K
# reference (overthink_q6k arm A). One fresh VERIFIED server per arm (AFM-50): stopped by name; its own log says
# loaded; /props names the arm's file; the offload line matches the placement. Resumable: a rep re-runs only the ids
# its jsonl lacks.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
H=10.0.0.194; PORT=8190; URL="http://$H:$PORT"
BIN='~/buun-0b278/build_sm60/bin/llama-server'
Q2='~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf'
IQ4='~/AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf'
FLAGS="-sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
OUT="$HERE/flashnext_stop"; mkdir -p "$OUT"; LOG="$OUT/run.log"
ALL="CAL-A1,CAL-A2,CAL-A3,CAL-A4,CAL-A5,CAL-A6,CAL-A7,CAL-A8,CAL-U1,CAL-U2,CAL-U3,CAL-U4,CAL-U5,CAL-U6,CAL-U7,CAL-U8"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

stop_server() {
  ssh "$H" 'pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1' \
    || { log "a llama-server survived pkill -- aborting"; exit 1; }
}

start_server() {   # ARM MODEL NGL -> 0 ours and verified; 1 died; 2 wrong server/placement
  local arm=$1 model=$2 ngl=$3
  stop_server
  ssh "$H" "CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $model -ngl $ngl $FLAGS > ~/fnstop_$arm.log 2>&1 < /dev/null &"
  local up=0
  for i in $(seq 1 120); do
    sleep 5
    ssh "$H" 'pgrep -x llama-server >/dev/null' || { log "$arm: server died: $(ssh "$H" "tail -3 ~/fnstop_$arm.log")"; return 1; }
    ssh "$H" "grep -q 'model loaded' ~/fnstop_$arm.log" && curl -sf -m 5 "$URL/health" >/dev/null && { up=1; break; }
  done
  [ $up = 1 ] || { log "$arm: not healthy after 600 s"; return 1; }
  local mp want
  mp=$(curl -s -m 5 "$URL/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$model")" ] || { log "$arm: WRONG SERVER: $mp"; return 2; }
  want=$([ "$ngl" = 99 ] && echo 49 || echo "$ngl")
  ssh "$H" "grep -q 'offloaded $want/49 layers to GPU' ~/fnstop_$arm.log" || { log "$arm: placement not $want/49"; return 2; }
  log "$arm: verified -- $want/49 on GPU, $(basename "$mp"), pid $(ssh "$H" 'pgrep -x llama-server'), gpus: $(ssh "$H" 'nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader' | sort -u | tr '\n' ' ')"
}

missing() {        # ids of ALL not yet in $1
  $PY - "$1" "$ALL" <<'EOF'
import json, os, sys
have = set()
if os.path.exists(sys.argv[1]):
    for l in open(sys.argv[1]):
        try: have.add(json.loads(l)["id"])
        except Exception: pass
print(",".join(i for i in sys.argv[2].split(",") if i not in have))
EOF
}

log "== flashnext stopping start"
for spec in "FNQ2|$Q2|99" "FNIQ4|$IQ4|44"; do
  IFS='|' read -r arm model ngl <<< "$spec"
  todo=0; for rep in 1 2 3; do [ -n "$(missing "$OUT/$arm/armA_rep$rep.jsonl")" ] && todo=1; done
  [ $todo = 0 ] && { log "$arm: complete, skipped"; continue; }
  start_server "$arm" "$model" "$ngl"; rc=$?
  [ $rc = 2 ] && { log "abort"; exit 1; }
  [ $rc = 0 ] || { log "$arm failed to start"; continue; }
  curl -s -m 600 "$URL/v1/chat/completions" -H 'content-type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"chat_template_kwargs":{"enable_thinking":false}}' >/dev/null
  mkdir -p "$OUT/$arm"
  for rep in 1 2 3; do
    ids=$(missing "$OUT/$arm/armA_rep$rep.jsonl"); [ -z "$ids" ] && continue
    log "$arm rep$rep: $ids"
    (cd "$HERE" && $PY -u run_fixture_structfix.py --host "$URL" --tier cal --effort xhigh --sampling card \
        --seed $((1000 + rep)) --only "$ids" --arm A --jsonl "$OUT/$arm/armA_rep$rep.jsonl") >> "$OUT/$arm/rep$rep.log" 2>&1
    log "$arm rep$rep: exit $? ($(wc -l < "$OUT/$arm/armA_rep$rep.jsonl") rows)"
  done
done
stop_server
log "== flashnext stopping done"
