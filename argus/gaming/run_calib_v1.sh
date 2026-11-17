#!/usr/bin/env bash
# CALIBRATION_v1.md driver, on the desktop: preflight P1-P4 on .194, then BASE's 20 calibration episodes on both lanes.
# Every server is checked (serves its file, returns a tool call) and gets one discarded warm-up request. Episodes run
# here (tools in bwrap); the models answer from .194. Powers .194 off at the end, whatever happened.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"; PY=$ROOT/venv_cachyos/bin/python3
H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'; DIR='~/AI/Models/qwopus'
OUT=$ROOT/data/receipts/agentic-gaming/calibration; RAW=$OUT/raw; PRE=$OUT/preflight.json
WORK=${CALIB_WORK:-/tmp/claude-1000/gaming_calib_v1}; LOG=$OUT/calib.log; mkdir -p "$RAW" "$OUT/preflight" "$WORK"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
declare -A FILE=([BASE]=Qwen3.8-27B-Q8_0.gguf [ARE]=Arete-27B-Q8_0.gguf [QWC]=Qwopus3.8-27B-Coder-Flash-Q8_0.gguf)

start() {   # start ARM GPUS PORT CTX
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $DIR/${FILE[$1]} -ngl 99 -sm layer -c $4 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0 --port $3 > ~/calib_$1_$3.log 2>&1 < /dev/null &"
  local i up=0
  for i in $(seq 1 120); do
    sleep 5
    curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }
    ssh "$H" "grep -qiE 'failed to allocate|out of memory|error loading|exiting due to|failed to load' ~/calib_$1_$3.log" && break
  done
  [ $up = 1 ] || { log "$1: no server on :$3 at -c $4 ($(ssh "$H" "grep -iE 'alloc|memory|error' ~/calib_$1_$3.log | tail -2" | tr '\n' ' ' | cut -c1-200))"; stop_port "$3"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "${FILE[$1]}" ] || { log "$1: WRONG or no server on :$3 ($mp)"; return 1; }
  $PY - "http://$H:$3" <<'PYEOF' || { log "$1: no tool call returned"; return 1; }
import json, sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
body = {"messages": [{"role": "user", "content": "List the files in the current directory."}], "tools": tools, "temperature": 0,
        "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
for k in range(2):                    # the first request after a load is a discarded warm-up; the second must be a tool call
    m = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json=body).json()["choices"][0]["message"]
print("tool call after warm-up:", json.dumps(m.get("tool_calls"))[:160])
sys.exit(0 if m.get("tool_calls") else 1)
PYEOF
  log "$1: verified on :$3 at -c $4 (${FILE[$1]}), warm-up discarded, tool call OK"
}
stop_port() { ssh "$H" "pid=\$(ss -ltnp 2>/dev/null | grep ':$1 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1); [ -n \"\$pid\" ] && [ \"\$(readlink /proc/\$pid/exe | xargs basename)\" = llama-server ] && kill \$pid; for i in \$(seq 1 30); do ss -ltn | grep -q ':$1 ' || exit 0; sleep 1; done"; }
finish() { ssh "$H" 'pkill -x llama-server; for i in $(seq 1 30); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done'; log "powering .194 off"; "$ROOT/tools/s194.sh" off >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
v1() { $PY "$HERE/run_v1.py" "$@" >> "$LOG" 2>&1; }

ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running on .194"; exit 1; }
log "== calibration v1 start (code $(git -C "$ROOT" rev-parse --short HEAD))"

# P1: the largest context BASE serves on one lane
CTX=""
for C in 49152 40960 32768; do start BASE 0,1 8190 $C && { CTX=$C; break; }; done
[ -n "$CTX" ] || { start BASE 0,1 8190 16384 || { log "ABORT: BASE does not serve even at 16384"; finish 1; }; CTX=16384; }
log "P1: context $CTX"; $PY -c "import json,sys; p='$PRE'; import os; d=json.load(open(p)) if os.path.exists(p) else {}; d['context']=$CTX; json.dump(d,open(p,'w'),indent=1)"

# P2 + P4: template and exit smoke, BASE on lane A, then ARE and QWC on lane B
SMOKE="f2v1:rle:TWIN:shallow:1 f2v1:rle:K1:shallow:1"
$PY "$HERE/preflight_v1.py" template BASE "http://$H:8190" "$PRE" >> "$LOG" 2>&1 || { log "ABORT: P2 template, BASE"; finish 1; }
start ARE 2,3 8191 $CTX || finish 1
$PY "$HERE/preflight_v1.py" template ARE "http://$H:8191" "$PRE" >> "$LOG" 2>&1 || { log "ABORT: P2 template, ARE"; finish 1; }
v1 BASE "http://$H:8190" "$OUT/preflight/BASE" "$WORK/pre" $SMOKE &
v1 ARE "http://$H:8191" "$OUT/preflight/ARE" "$WORK/pre" $SMOKE &
wait; log "P4: BASE and ARE smoke done"; stop_port 8191
start QWC 2,3 8191 $CTX || finish 1
$PY "$HERE/preflight_v1.py" template QWC "http://$H:8191" "$PRE" >> "$LOG" 2>&1 || { log "ABORT: P2 template, QWC"; finish 1; }
v1 QWC "http://$H:8191" "$OUT/preflight/QWC" "$WORK/pre" $SMOKE; log "P4: QWC smoke done"; stop_port 8191

# P3: the same item at CTX and at 16384 must give byte-identical transcripts
start BASE 2,3 8191 16384 || finish 1
LEAK=f2v1:ranges:K1:deep:1
v1 BASE "http://$H:8190" "$OUT/preflight/leak_ctx" "$WORK/leakA" $LEAK &
v1 BASE "http://$H:8191" "$OUT/preflight/leak_16k" "$WORK/leakB" $LEAK &
wait
$PY "$HERE/preflight_v1.py" leak "$OUT/preflight/leak_ctx/f2v1_ranges_K1_deep_1.json" "$OUT/preflight/leak_16k/f2v1_ranges_K1_deep_1.json" >> "$LOG" 2>&1 \
  || { log "ABORT: P3 transcripts differ between contexts"; finish 1; }
log "P3: identical at $CTX and 16384"; stop_port 8191

# Calibration: BASE on both lanes at CTX; each replay copy runs on its original's lane, after it
start BASE 2,3 8191 $CTX || finish 1
A="f2v1:ranges:K1:deep:1 f2v1:ranges:K2:deep:1 f2v1:ranges:TWIN:deep:1 f2v1:ranges:TWIN:deep:1#r2 f2v1:ranges:K1:shallow:1 f2v1:ranges:K2:shallow:1 f2v1:ranges:TWIN:shallow:1 bridge:B1:1 k3:TWIN:deep:1 k3:K3:shallow:1"
B="f2v1:rle:K1:deep:1 f2v1:rle:K2:deep:1 f2v1:rle:TWIN:deep:1 f2v1:rle:K1:shallow:1 f2v1:rle:K1:shallow:1#r2 f2v1:rle:K2:shallow:1 f2v1:rle:TWIN:shallow:1 bridge:B2:1 k3:K3:deep:1 k3:K3:deep:1#r2"
log "calibration: 20 episodes on two lanes"
v1 BASE "http://$H:8190" "$RAW/BASE" "$WORK/calA" $A &
v1 BASE "http://$H:8191" "$RAW/BASE" "$WORK/calB" $B &
wait
log "calibration episodes: $(ls "$RAW/BASE" | wc -l) of 20"
finish 0
