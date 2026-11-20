#!/usr/bin/env bash
# PREREG_SEED2.md driver: powers .194 on, BASE on GPUs 0+1 and PIA (base + pi LoRA) on 2+3, preflight, then the ten
# seed-2 v1 items per arm with thinking on at xhigh, reasoning replayed, greedy, 16k per step (episode wall 13 h), then the
# preserved-reasoning probe on the same servers (until 14.5 h from the start). Powers .194 off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'
BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; LORA='~/AI/Models/pi-adapter/Qwen3.8-27B-pi-lora-F16.gguf'
LORA_SHA=a64f91844f19e67da500d8628bdf9383aa334e61b7ab687805802e7d272d7b67
FLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
OUT=$HERE/seed2; WORK=/tmp/claude-1000/gaming_think_s2; LOG=$OUT/seed2.log; mkdir -p "$OUT/raw" "$WORK"
WALL=$((13 * 3600)); TOTAL=$((29 * 1800))
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

T_START=$(date +%s)
log "== thinking seed 2 start (code $(git -C "$ROOT" rev-parse --short HEAD))"
"$ROOT/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
# First launch (19:27): sshd reset connections seconds after boot, so the next checks got nothing. Wait until a real
# command answers three times in a row, 10 s apart, and make every check fail closed.
ok=0; for i in $(seq 1 40); do
  if [ "$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" 'echo ready' 2>/dev/null)" = ready ]; then ok=$((ok + 1)); else ok=0; fi
  [ $ok -ge 3 ] && break; sleep 10
done
[ $ok -ge 3 ] || { log "ABORT: ssh to .194 not stable after boot"; finish 1; }
log "ssh stable"
st=$(ssh "$H" 'pgrep -x llama-server >/dev/null && echo RUNNING || echo CLEAR' 2>/dev/null)
[ "$st" = CLEAR ] || { log "ABORT: llama-server check returned '$st'"; finish 1; }
h=$(ssh "$H" "sha256sum $LORA | cut -d' ' -f1"); [ "$h" = "$LORA_SHA" ] || { log "ABORT: adapter hash $h"; finish 1; }
start BASE 0,1 8190 0 && start PIA 2,3 8191 1 || finish 1
$PY "$HERE/preflight_think.py" BASE "http://$H:8190" "$OUT/preflight.json" >> "$LOG" 2>&1 \
  && $PY "$HERE/preflight_think.py" PIA "http://$H:8191" "$OUT/preflight.json" >> "$LOG" 2>&1 \
  || { log "ABORT: preflight failed (see preflight.json)"; finish 1; }
log "preflight passed on both"

ITEMS="f2v1:rle:TWIN:shallow:2 f2v1:ranges:TWIN:shallow:2 k3:TWIN:shallow:2 k3:K3:shallow:2 f2v1:rle:K1:shallow:2 f2v1:ranges:K2:shallow:2 f2v1:rle:K2:shallow:2 k3:K3:deep:2 f2v1:rle:K1:deep:2 f2v1:ranges:K1:shallow:2"
export THINK=xhigh MAX_TOKENS=16384 REQ_TIMEOUT=3600 KEEP_REASONING=1
lane() {   # ARM PORT WORKDIR: the episodes (13 h wall from their start), then this lane's probe until 14.5 h from T_START
  timeout "$WALL" $PY "$ROOT/argus/gaming/run_v1.py" "$1" "http://$H:$2" "$OUT/raw/$1" "$WORK/$3" $ITEMS >> "$LOG" 2>&1
  local rc=$?; [ $rc = 124 ] && log "$1: episode wall limit reached (checkpoints kept)"
  log "$1: episodes done, $(ls "$OUT/raw/$1" 2>/dev/null | grep -vc partial) of 10"
  local left=$(( TOTAL - ($(date +%s) - T_START) ))
  if [ $left -gt 600 ]; then
    timeout "$left" $PY "$HERE/probe_preserve.py" "http://$H:$2" "$OUT/raw/$1" "$OUT/probe_$1.jsonl" >> "$LOG" 2>&1
    log "$1: probe exit $?, $(cat "$OUT/probe_$1.jsonl" 2>/dev/null | wc -l) rows"
  else
    log "$1: probe skipped, no time left"
  fi
}
lane BASE 8190 A &
PA=$!
lane PIA 8191 B &
PB=$!
echo "$PA $PB" > "$OUT/lane.pids"
wait "$PA" "$PB"
finish 0
