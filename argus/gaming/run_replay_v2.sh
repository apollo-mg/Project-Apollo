#!/usr/bin/env bash
# REPLAY_GATE_v2.md driver: two items, each run twice on its own lane of .194, then compared. Powers .194 off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; PY=$ROOT/venv_cachyos/bin/python3
H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'; DIR='~/AI/Models/qwopus'
OUT=$ROOT/data/receipts/agentic-gaming/replay_v2; RAW=$OUT/raw/BASE; LOG=$OUT/replay.log
WORK=${REPLAY_WORK:-/tmp/claude-1000/gaming_replay_v2}; mkdir -p "$RAW" "$WORK"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
start() {   # GPUS PORT
  ssh "$H" "CUDA_VISIBLE_DEVICES=$1 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $DIR/Qwen3.8-27B-Q8_0.gguf -ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0 --port $2 > ~/replay_$2.log 2>&1 < /dev/null &"
  local i; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$2/health" >/dev/null && break; done
  $PY - "http://$H:$2" <<'PYEOF' || return 1
import json, sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
body = {"messages": [{"role": "user", "content": "List the files in the current directory."}], "tools": tools, "temperature": 0, "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
for k in range(2):
    m = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json=body).json()["choices"][0]["message"]
sys.exit(0 if m.get("tool_calls") else 1)
PYEOF
  log "BASE verified on :$2, warm-up discarded"
}
finish() { "$HERE/stop_194.sh" >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running"; exit 1; }
log "== replay gate v2 start (code $(git -C "$ROOT" rev-parse --short HEAD))"
start 0,1 8190 || finish 1; start 2,3 8191 || finish 1
$PY "$HERE/run_v1.py" BASE "http://$H:8190" "$RAW" "$WORK/A" "f2v1:rle:K1:shallow:1" "f2v1:rle:K1:shallow:1#r2" >> "$LOG" 2>&1 &
$PY "$HERE/run_v1.py" BASE "http://$H:8191" "$RAW" "$WORK/B" "k3:K3:deep:1" "k3:K3:deep:1#r2" >> "$LOG" 2>&1 &
wait
rc=0
for pair in "f2v1_rle_K1_shallow_1" "k3_K3_deep_1"; do
  $PY "$HERE/preflight_v1.py" leak "$RAW/$pair.json" "$RAW/${pair}_r2.json" >> "$LOG" 2>&1 && log "PASS $pair" || { log "FAIL $pair"; rc=2; }
done
finish $rc
