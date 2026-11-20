#!/usr/bin/env bash
# PLAN_SIZING.md driver: powers .194 on, BASE on GPUs 0+1 and PIA (base + pi LoRA) on 2+3, preflight, then two v1 items
# per arm with thinking on at xhigh, reasoning replayed, greedy, 16k per step. Wall limit 7 h. Powers .194 off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'
BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; LORA='~/AI/Models/pi-adapter/Qwen3.8-27B-pi-lora-F16.gguf'
LORA_SHA=a64f91844f19e67da500d8628bdf9383aa334e61b7ab687805802e7d272d7b67
FLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
OUT=$HERE/sizing; WORK=/tmp/claude-1000/gaming_think; LOG=$OUT/sizing.log; mkdir -p "$OUT/raw" "$WORK"
WALL=$((7 * 3600))
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
finish() { "$ROOT/argus/gaming/stop_194.sh" >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
start() {   # ARM GPUS PORT LORA(0/1)
  local extra=""; [ "$4" = 1 ] && extra="--lora $LORA"
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $BASE_F $extra $FLAGS --port $3 > ~/think_$1_$3.log 2>&1 < /dev/null &"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$1: not healthy on :$3"; return 1; }
  local n; n=$(curl -s -m 5 "http://$H:$3/lora-adapters" | $PY -c 'import json,sys; print(len(json.load(sys.stdin)))')
  [ "$n" = "$4" ] || { log "$1: expected $4 adapter(s) on :$3, found $n"; return 1; }
  $PY - "http://$H:$3" <<'PYEOF' || { log "$1: no tool call on :$3"; return 1; }
import sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
body = {"messages": [{"role": "user", "content": "List the files in the current directory."}], "tools": tools, "temperature": 0, "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
for k in range(2):   # the first is the discarded warm-up
    m = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json=body).json()["choices"][0]["message"]
sys.exit(0 if m.get("tool_calls") else 1)
PYEOF
  log "$1: up on :$3 ($n adapter), tool call verified, warm-up discarded"
}

log "== thinking sizing start (code $(git -C "$ROOT" rev-parse --short HEAD))"
"$ROOT/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running"; finish 1; }
h=$(ssh "$H" "sha256sum $LORA | cut -d' ' -f1"); [ "$h" = "$LORA_SHA" ] || { log "ABORT: adapter hash $h"; finish 1; }
start BASE 0,1 8190 0 && start PIA 2,3 8191 1 || finish 1
$PY "$HERE/preflight_think.py" BASE "http://$H:8190" "$OUT/preflight.json" >> "$LOG" 2>&1 \
  && $PY "$HERE/preflight_think.py" PIA "http://$H:8191" "$OUT/preflight.json" >> "$LOG" 2>&1 \
  || { log "ABORT: preflight failed (see preflight.json)"; finish 1; }
log "preflight passed on both"

ITEMS="f2v1:rle:TWIN:shallow:2 k3:K3:shallow:2"
export THINK=xhigh MAX_TOKENS=16384 REQ_TIMEOUT=3600 KEEP_REASONING=1
$PY "$ROOT/argus/gaming/run_v1.py" BASE "http://$H:8190" "$OUT/raw/BASE" "$WORK/A" $ITEMS >> "$LOG" 2>&1 &
PA=$!
$PY "$ROOT/argus/gaming/run_v1.py" PIA "http://$H:8191" "$OUT/raw/PIA" "$WORK/B" $ITEMS >> "$LOG" 2>&1 &
PB=$!
echo "$PA $PB" > "$OUT/runner.pids"
T0=$(date +%s)
while kill -0 "$PA" 2>/dev/null || kill -0 "$PB" 2>/dev/null; do
  sleep 30
  if [ $(( $(date +%s) - T0 )) -gt $WALL ]; then
    log "wall limit reached: stopping the runners (checkpoints are kept)"; kill "$PA" "$PB" 2>/dev/null; sleep 5; break
  fi
done
log "episodes: BASE $(ls "$OUT/raw/BASE" 2>/dev/null | grep -vc partial), PIA $(ls "$OUT/raw/PIA" 2>/dev/null | grep -vc partial) of 2 each"
finish 0
