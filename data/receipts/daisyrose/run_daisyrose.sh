#!/usr/bin/env bash
# PREREG_DAISYROSE.md driver (desktop): after the verified download, convert DaisyRose-27B to Q8_0 (llama.cpp 67107ac34f,
# as Arete), record the tensor map, power .194 on, stage and hash-check, phase 1 M1 (DRS vs base replay C.R4, prompt
# gate), phase 2 the 30 agentic items thinking off (DRS on both lanes). Powers .194 off at the end.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; LC=$ROOT/engines/llama_cpp_67107ac; H=10.0.0.194
SRC=/mnt/HDD/daisyrose-27b; OUTD=/mnt/TG_2TB/AI/Models/daisyrose-27b-gguf; OUT=$OUTD/DaisyRose-27B-Q8_0.gguf
BASE_LOCAL=/mnt/TG_2TB/AI/Models/qwen38-27b-ref/Qwen3.8-27B-Q8_0.gguf
BIN='~/buun-0b278/build_sm60/bin/llama-server'; BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'
BASE_SHA=a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348
M1FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0"
AGFLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
LOG=$HERE/daisyrose.log; mkdir -p "$OUTD" "$QA/raw/logs"
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
finish() { "$ROOT/argus/gaming/stop_194.sh" >> "$LOG" 2>&1; log "== DONE ($1)"; exit "$1"; }
stop_port() { ssh "$H" "pid=\$(ss -ltnp 2>/dev/null | grep ':$1 ' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1); [ -n \"\$pid\" ] && [ \"\$(readlink /proc/\$pid/exe | xargs basename)\" = llama-server ] && kill \$pid; for i in \$(seq 1 30); do ss -ltn | grep -q ':$1 ' || exit 0; sleep 1; done; exit 1"; }
start() {   # NAME GPUS PORT FILE FLAGS TOOLCHECK(0/1)
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $4 $5 --port $3 > ~/daisy_$1_$3.log 2>&1 < /dev/null &"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$1: not healthy on :$3"; return 1; }
  local mp; mp=$(curl -s -m 5 "http://$H:$3/props" | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  [ "$(basename "$mp")" = "$(basename "$4")" ] || { log "$1: WRONG model on :$3 ($mp)"; return 1; }
  if [ "$6" = 1 ]; then
    $PY - "http://$H:$3" <<'PYEOF' || { log "$1: no tool call on :$3"; return 1; }
import sys, httpx
tools = [{"type": "function", "function": {"name": "list_dir", "description": "List a directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]
body = {"messages": [{"role": "user", "content": "List the files in the current directory."}], "tools": tools, "temperature": 0, "max_tokens": 512, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
for k in range(2):   # the first is the discarded warm-up
    m = httpx.post(sys.argv[1] + "/v1/chat/completions", timeout=600, json=body).json()["choices"][0]["message"]
sys.exit(0 if m.get("tool_calls") else 1)
PYEOF
  fi
  log "$1: up on :$3 ($(basename "$4"))$([ "$6" = 1 ] && echo ", tool call verified, warm-up discarded")"
}

log "== DaisyRose run start (code $(git -C "$ROOT" rev-parse --short HEAD))"
# 1. the file
while [ "$(systemctl --user show daisy-dl -p ActiveState --value 2>/dev/null)" = active ]; do sleep 60; done
tail -1 "$SRC/download.log" | grep -q "ALL OK$" || { log "ABORT: download did not end ALL OK: $(tail -1 "$SRC/download.log")"; exit 1; }
if [ ! -s "$OUT" ]; then
  log "converting to Q8_0"
  (cd /tmp && "$PY" "$LC/convert_hf_to_gguf.py" "$SRC" --outtype q8_0 --outfile "$OUT" > "$OUTD/convert.log" 2>&1) \
    || { log "ABORT: convert failed: $(tail -2 "$OUTD/convert.log" | tr '\n' ' ')"; exit 1; }
fi
DR_SHA=$(sha256sum "$OUT" | cut -d' ' -f1); DR_SIZE=$(stat -c %s "$OUT"); log "Q8_0 $DR_SIZE bytes sha256 $DR_SHA"
"$PY" -I "$HERE/../arete/tensor_map.py" "$LC/gguf-py" "$OUT" "$BASE_LOCAL" > "$HERE/tensor_map.txt" 2>&1; log "tensor map: $(sed -n 3p "$HERE/tensor_map.txt")"

# 2. .194: power, stable ssh, staging
"$ROOT/tools/s194.sh" on >> "$LOG" 2>&1 || { log "ABORT: .194 did not come up"; exit 1; }
ok=0; for i in $(seq 1 40); do
  if [ "$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$H" 'echo ready' 2>/dev/null)" = ready ]; then ok=$((ok + 1)); else ok=0; fi
  [ $ok -ge 3 ] && break; sleep 10
done
[ $ok -ge 3 ] || { log "ABORT: ssh to .194 not stable after boot"; finish 1; }
st=$(ssh "$H" 'pgrep -x llama-server >/dev/null && echo RUNNING || echo CLEAR' 2>/dev/null)
[ "$st" = CLEAR ] || { log "ABORT: llama-server check returned '$st'"; finish 1; }
free=$(ssh "$H" 'df --output=avail -B1 ~/AI/Models/qwopus | tail -1')
if [ -n "$free" ] && [ "$free" -gt $((DR_SIZE + 6000000000)) ]; then DR_DIR='~/AI/Models/qwopus'; else DR_DIR=/dev/shm/daisyrose; ssh "$H" "mkdir -p $DR_DIR"; fi
DR_F="$DR_DIR/DaisyRose-27B-Q8_0.gguf"
log ".194 disk free $free bytes -> staging in $DR_DIR"
if [ "$(ssh "$H" "sha256sum $DR_F 2>/dev/null" | cut -d' ' -f1)" != "$DR_SHA" ]; then
  scp -q "$OUT" "$H:${DR_F/#\~\//}" || { log "ABORT: scp failed"; finish 1; }
fi
for spec in "$DR_F|$DR_SHA" "$BASE_F|$BASE_SHA"; do
  IFS='|' read -r f want <<< "$spec"
  got=$(ssh "$H" "sha256sum $f" | cut -d' ' -f1); [ "$got" = "$want" ] || { log "ABORT: HASH MISMATCH $f: $got"; finish 1; }
done
log "hashes verified on .194"

# 3. phase 1: M1
start DRS 0,1 8190 "$DR_F" "$M1FLAGS" 0 && start C.R4 2,3 8191 "$BASE_F" "$M1FLAGS" 0 || finish 1
ga=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8190"); gb=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8191")
log "prompt gate DRS $ga | C.R4 $gb"; [ -n "$ga" ] && [ "$ga" = "$gb" ] || { log "ABORT: prompts differ"; finish 1; }
m1() {   # ARM PORT GPUS FILE SHA
  local tail; tail=$(cat "$QA/raw/logs/ar_expect_tail.txt"; printf x); tail=${tail%x}
  local meta; meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host"], sys.argv[1:]))))' \
    "$1" "$4" "$5" 0b2789f23f5ac10ed9a99aeb40ed10d3ba1c0163 "$M1FLAGS --port $2" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal" ".194")
  $PY "$QA/run_main.py" --url "http://$H:$2" --arm "$1" --meta "$meta" --usage \
    --expect-variants "$(cat "$QA/raw/logs/ar_expect_variants.json")" --expect-render-tail "$tail" > "$QA/raw/logs/daisy_run_$1.log" 2>&1
  log "$1: run_main exit $? ($(( $(wc -l < "$QA/raw/main_$1.jsonl") - 1 )) rows)"
}
m1 DRS 8190 0,1 "$DR_F" "$DR_SHA" & m1 C.R4 8191 2,3 "$BASE_F" "$BASE_SHA" & wait
stop_port 8190 && stop_port 8191 || { log "ABORT: M1 servers did not stop"; finish 1; }

# 4. phase 2: the agentic items, DRS on both lanes, thinking off
OUT2=$ROOT/data/receipts/agentic-gaming/main; WORK=/tmp/claude-1000/gaming_daisy
start DRS 0,1 8190 "$DR_F" "$AGFLAGS" 1 && start DRS 2,3 8191 "$DR_F" "$AGFLAGS" 1 || finish 1
A=""; B=""
for s in 2 3 4; do
  A="$A f2v1:rle:K1:deep:$s f2v1:ranges:K1:shallow:$s k3:K3:deep:$s f2v1:rle:TWIN:shallow:$s k3:TWIN:shallow:$s"
  B="$B f2v1:rle:K1:shallow:$s f2v1:rle:K2:shallow:$s f2v1:ranges:K2:shallow:$s k3:K3:shallow:$s f2v1:ranges:TWIN:shallow:$s"
done
$PY "$ROOT/argus/gaming/run_v1.py" DRS "http://$H:8190" "$OUT2/raw/DRS" "$WORK/A" $A >> "$LOG" 2>&1 &
PA=$!
$PY "$ROOT/argus/gaming/run_v1.py" DRS "http://$H:8191" "$OUT2/raw/DRS" "$WORK/B" $B >> "$LOG" 2>&1 &
PB=$!
echo "$PA $PB" > "$HERE/runner.pids"
wait "$PA" "$PB"
log "DRS agentic: $(ls "$OUT2/raw/DRS" | grep -vc partial) of 30 episodes"
finish 0
