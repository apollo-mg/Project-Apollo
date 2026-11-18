#!/usr/bin/env bash
# PREREG_MAIN_v1.md driver: BASE, ARE, QWC in turn, each on both lanes of .194 with its 30 items split, then off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; PY=$ROOT/venv_cachyos/bin/python3
H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'; DIR='~/AI/Models/qwopus'
OUT=$ROOT/data/receipts/agentic-gaming/main; LOG=$OUT/main.log; WORK=${MAIN_WORK:-/tmp/claude-1000/gaming_main_v1}
mkdir -p "$OUT/raw" "$WORK"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
declare -A FILE=([BASE]=Qwen3.8-27B-Q8_0.gguf [ARE]=Arete-27B-Q8_0.gguf [QWC]=Qwopus3.8-27B-Coder-Flash-Q8_0.gguf)
start() {   # ARM GPUS PORT
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $DIR/${FILE[$1]} -ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0 --port $3 > ~/main_$1_$3.log 2>&1 < /dev/null &"
  local i; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && break; done
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "${FILE[$1]}" ] || { log "$1: WRONG or no server on :$3 ($mp)"; return 1; }
  $PY - "http://$H:$3" <<'PYEOF' || { log "$1: no tool call on :$3"; return 1; }
import json, sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
body = {"messages": [{"role": "user", "content": "List the files in the current directory."}], "tools": tools, "temperature": 0, "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
for k in range(2):
    m = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json=body).json()["choices"][0]["message"]
sys.exit(0 if m.get("tool_calls") else 1)
PYEOF
  log "$1: verified on :$3 (${FILE[$1]}), warm-up discarded"
}
stop_port() { ssh "$H" "pid=\$(ss -ltnp 2>/dev/null | grep ':$1 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1); [ -n \"\$pid\" ] && [ \"\$(readlink /proc/\$pid/exe | xargs basename)\" = llama-server ] && kill \$pid; for i in \$(seq 1 30); do ss -ltn | grep -q ':$1 ' || exit 0; sleep 1; done"; }
finish() { "$HERE/stop_194.sh" >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
A=""; B=""
for s in 2 3 4; do      # each lane gets a balanced half of every seed's ten items
  A="$A f2v1:rle:K1:deep:$s f2v1:ranges:K1:shallow:$s k3:K3:deep:$s f2v1:rle:TWIN:shallow:$s k3:TWIN:shallow:$s"
  B="$B f2v1:rle:K1:shallow:$s f2v1:rle:K2:shallow:$s f2v1:ranges:K2:shallow:$s k3:K3:shallow:$s f2v1:ranges:TWIN:shallow:$s"
done
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running"; exit 1; }
log "== main run v1 start (code $(git -C "$ROOT" rev-parse --short HEAD))"
for ARM in BASE ARE QWC; do
  start $ARM 0,1 8190 && start $ARM 2,3 8191 || finish 1
  $PY "$HERE/run_v1.py" $ARM "http://$H:8190" "$OUT/raw/$ARM" "$WORK/$ARM-A" $A >> "$LOG" 2>&1 &
  $PY "$HERE/run_v1.py" $ARM "http://$H:8191" "$OUT/raw/$ARM" "$WORK/$ARM-B" $B >> "$LOG" 2>&1 &
  wait
  log "$ARM: $(ls "$OUT/raw/$ARM" | grep -vc partial) of 30 episodes"
  stop_port 8190; stop_port 8191; sleep 5
done
finish 0
