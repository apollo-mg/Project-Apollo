#!/usr/bin/env bash
# PILOT_v0.md driver, on the desktop: BASE (GPUs 0+1, :8190) and ARE (GPUs 2+3, :8191) at the same time, then QWC on
# GPUs 0+1. Each server is verified (it serves its file) and must return a real tool call before its episodes start.
# Episodes run here (tools in bwrap); the models answer from .194. Powers .194 off at the end.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; PY=$ROOT/venv_cachyos/bin/python3
H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'; DIR='~/AI/Models/qwopus'
FLAGS="-ngl 99 -sm layer -c 16384 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
OUT=$ROOT/data/receipts/agentic-gaming/pilot/raw; WORK=${PILOT_WORK:-/tmp/claude-1000/gaming_pilot}
LOG=$ROOT/data/receipts/agentic-gaming/pilot/pilot.log; mkdir -p "$OUT" "$WORK"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
declare -A FILE=([BASE]=Qwen3.8-27B-Q8_0.gguf [ARE]=Arete-27B-Q8_0.gguf [QWC]=Qwopus3.8-27B-Coder-Flash-Q8_0.gguf)

start() {   # start ARM GPUS PORT
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $DIR/${FILE[$1]} $FLAGS --port $3 > ~/pilot_$1.log 2>&1 < /dev/null &"
  local i; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && break; done
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "${FILE[$1]}" ] || { log "$1: WRONG or no server on :$3 ($mp)"; return 1; }
  $PY - "http://$H:$3" <<'EOF' || { log "$1: no tool call returned"; return 1; }
import json, sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
r = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json={"messages": [{"role": "user", "content": "List the files in the current directory."}],
               "tools": tools, "temperature": 0, "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}})
m = r.json()["choices"][0]["message"]; print("smoke tool call:", json.dumps(m.get("tool_calls"))[:200])
sys.exit(0 if m.get("tool_calls") else 1)
EOF
  log "$1: verified on :$3 (${FILE[$1]}), tool call OK"
}
stop_port() { ssh "$H" "pid=\$(ss -ltnp 2>/dev/null | grep ':$1 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1); [ -n \"\$pid\" ] && [ \"\$(readlink /proc/\$pid/exe | xargs basename)\" = llama-server ] && kill \$pid"; }

ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "a llama-server is already running on .194 -- aborting"; exit 1; }
log "== pilot start"
start BASE 0,1 8190 && start ARE 2,3 8191 || { ssh "$H" 'pkill -x llama-server'; exit 1; }
$PY "$HERE/run_pilot.py" BASE "http://$H:8190" "$OUT/BASE" "$WORK" >> "$LOG" 2>&1 &
$PY "$HERE/run_pilot.py" ARE "http://$H:8191" "$OUT/ARE" "$WORK" >> "$LOG" 2>&1 &
wait
log "phase 1 done"; stop_port 8190; stop_port 8191; sleep 10
start QWC 0,1 8190 || { ssh "$H" 'pkill -x llama-server'; exit 1; }
$PY "$HERE/run_pilot.py" QWC "http://$H:8190" "$OUT/QWC" "$WORK" >> "$LOG" 2>&1
ssh "$H" 'pkill -x llama-server; for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done'
log "== pilot done; powering .194 off"
"$ROOT/tools/s194.sh" off >> "$LOG" 2>&1
