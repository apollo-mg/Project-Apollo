#!/usr/bin/env bash
# PREREG_SENTENCE.md driver: power on, both servers on the original template -> references -> restart on the patched
# template -> byte gates -> control (switch off) -> ten seed-2 items per arm, thinking off + the xhigh sentence. Power off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'
BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; LORA='~/AI/Models/pi-adapter/Qwen3.8-27B-pi-lora-F16.gguf'
LORA_SHA=a64f91844f19e67da500d8628bdf9383aa334e61b7ab687805802e7d272d7b67
FLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
OUT=$HERE/sentence; WORK=/tmp/claude-1000/gaming_sentence; LOG=$OUT/sentence.log; mkdir -p "$OUT/raw" "$OUT/control" "$WORK"
WALL=$((5 * 3600)); TPL='~/sentence_template.jinja'
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
finish() { "$ROOT/argus/gaming/stop_194.sh" >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
start() {   # ARM GPUS PORT LORA(0/1) EXTRA_FLAGS
  local extra=""; [ "$4" = 1 ] && extra="--lora $LORA"
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $BASE_F $extra $FLAGS $5 --port $3 > ~/sentence_$1_$3.log 2>&1 < /dev/null &"
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
  log "$1: up on :$3 ($n adapter${5:+, $5}), tool call verified, warm-up discarded"
}
stop_port() { ssh "$H" "pid=\$(ss -ltnp 2>/dev/null | grep ':$1 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1); [ -n \"\$pid\" ] && [ \"\$(readlink /proc/\$pid/exe | xargs basename)\" = llama-server ] && kill \$pid; for i in \$(seq 1 30); do ss -ltn | grep -q ':$1 ' || exit 0; sleep 1; done; exit 1"; }

log "== sentence cell start (code $(git -C "$ROOT" rev-parse --short HEAD))"
"$ROOT/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
ok=0; for i in $(seq 1 40); do
  if [ "$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" 'echo ready' 2>/dev/null)" = ready ]; then ok=$((ok + 1)); else ok=0; fi
  [ $ok -ge 3 ] && break; sleep 10
done
[ $ok -ge 3 ] || { log "ABORT: ssh to .194 not stable after boot"; finish 1; }
log "ssh stable; memory: $(ssh "$H" 'free -b | sed -n 2p' | awk '{printf "total %.1f GiB, available %.1f GiB", $2/2^30, $7/2^30}')"
st=$(ssh "$H" 'pgrep -x llama-server >/dev/null && echo RUNNING || echo CLEAR' 2>/dev/null)
[ "$st" = CLEAR ] || { log "ABORT: llama-server check returned '$st'"; finish 1; }
h=$(ssh "$H" "sha256sum $LORA | cut -d' ' -f1"); [ "$h" = "$LORA_SHA" ] || { log "ABORT: adapter hash $h"; finish 1; }

# 1. references from the original template
start BASE 0,1 8190 0 "" && start PIA 2,3 8191 1 "" || finish 1
for a in BASE:8190 PIA:8191; do
  $PY "$HERE/sentence_template.py" capture "http://$H:${a#*:}" "$OUT/ref_${a%%:*}.json" >> "$LOG" 2>&1 || { log "ABORT: capture ${a%%:*}"; finish 1; }
  curl -s -m 20 "http://$H:${a#*:}/props" | $PY -c 'import json,sys; sys.stdout.write(json.load(sys.stdin)["chat_template"])' > "$OUT/template_original_${a%%:*}.jinja"
done
cmp -s "$OUT/template_original_BASE.jinja" "$OUT/template_original_PIA.jinja" || { log "ABORT: the two servers serve different templates"; finish 1; }
$PY "$HERE/sentence_template.py" patch "$OUT/template_original_BASE.jinja" "$OUT/template_patched.jinja" >> "$LOG" 2>&1 || { log "ABORT: patch"; finish 1; }
scp -q "$OUT/template_patched.jinja" "$H:sentence_template.jinja" || { log "ABORT: scp"; finish 1; }
stop_port 8190 && stop_port 8191 || { log "ABORT: servers did not stop"; finish 1; }
log "references captured, template patched ($(diff "$OUT/template_original_BASE.jinja" "$OUT/template_patched.jinja" | grep -c '^>') line changed)"

# 2. patched template: gates
start BASE 0,1 8190 0 "--chat-template-file $TPL" && start PIA 2,3 8191 1 "--chat-template-file $TPL" || finish 1
for a in BASE:8190 PIA:8191; do
  $PY "$HERE/sentence_template.py" check "http://$H:${a#*:}" "$OUT/ref_${a%%:*}.json" >> "$LOG" 2>&1 || { log "ABORT: template gate failed on ${a%%:*}"; finish 1; }
done
log "template gates passed on both"

# 3. per lane: control (switch off), then the ten items with the sentence
ITEMS="f2v1:rle:TWIN:shallow:2 f2v1:ranges:TWIN:shallow:2 k3:TWIN:shallow:2 k3:K3:shallow:2 f2v1:rle:K1:shallow:2 f2v1:ranges:K2:shallow:2 f2v1:rle:K2:shallow:2 k3:K3:deep:2 f2v1:rle:K1:deep:2 f2v1:ranges:K1:shallow:2"
lane() {   # ARM PORT WORKDIR
  $PY "$ROOT/argus/gaming/run_v1.py" "$1" "http://$H:$2" "$OUT/control/$1" "$WORK/$3-ctl" f2v1:rle:TWIN:shallow:2 >> "$LOG" 2>&1
  log "$1: control done"
  TEMPLATE_KWARGS_EXTRA='{"reasoning_effort": "xhigh", "force_effort_instructions": true}' \
    timeout "$WALL" $PY "$ROOT/argus/gaming/run_v1.py" "$1" "http://$H:$2" "$OUT/raw/$1" "$WORK/$3" $ITEMS >> "$LOG" 2>&1
  [ $? = 124 ] && log "$1: wall limit reached (checkpoints kept)"
  log "$1: episodes done, $(ls "$OUT/raw/$1" 2>/dev/null | grep -vc partial) of 10"
}
lane BASE 8190 A &
PA=$!
lane PIA 8191 B &
PB=$!
echo "$PA $PB" > "$OUT/lane.pids"
wait "$PA" "$PB"
finish 0
