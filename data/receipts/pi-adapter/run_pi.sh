#!/usr/bin/env bash
# PREREG_PI_ADAPTER.md driver. Phase 1: M1 for PIA (base + the pi LoRA) and C.R3 (base replay) on the two lanes, with
# the Arete run's settings and gates. Phase 2: the agentic main-run items for PIA on both lanes. Powers .194 off.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; QA="$HERE/../quant-abstention"; ROOT="$(cd "$HERE/../../.." && pwd)"
PY=$ROOT/venv_cachyos/bin/python3; H=10.0.0.194; BIN='~/buun-0b278/build_sm60/bin/llama-server'
BASE_F='~/AI/Models/qwopus/Qwen3.8-27B-Q8_0.gguf'; LORA='~/AI/Models/pi-adapter/Qwen3.8-27B-pi-lora-F16.gguf'
BASE_SHA=a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348
LORA_SHA=a64f91844f19e67da500d8628bdf9383aa334e61b7ab687805802e7d272d7b67
M1FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0"
AGFLAGS="-ngl 99 -sm layer -c 49152 -ctk f16 -ctv f16 -np 1 -fit off --jinja --host 0.0.0.0"
LOG=$HERE/pi.log
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
start() {   # NAME GPUS PORT FLAGS LORA(0/1)
  local extra=""; [ "$5" = 1 ] && extra="--lora $LORA"
  ssh "$H" "CUDA_VISIBLE_DEVICES=$2 GGML_CUDA_ALLREDUCE=internal nohup $BIN -m $BASE_F $extra $4 --port $3 > ~/pi_$1_$3.log 2>&1 < /dev/null &"
  local i up=0; for i in $(seq 1 120); do sleep 5; curl -sf -m 5 "http://$H:$3/health" >/dev/null && { up=1; break; }; done
  [ $up = 1 ] || { log "$1: not healthy on :$3"; return 1; }
  local n; n=$(curl -s -m 5 "http://$H:$3/lora-adapters" | $PY -c 'import json,sys; print(len(json.load(sys.stdin)))')
  [ "$n" = "$5" ] || { log "$1: expected $5 adapter(s) on :$3, found $n"; return 1; }
  log "$1: up on :$3 ($n adapter)"
}
stop_all() { "$ROOT/argus/gaming/stop_194.sh" >> "$LOG" 2>&1 || true; }
finish() { log "== DONE ($1)"; exit "$1"; }
ssh "$H" 'pgrep -x llama-server >/dev/null' && { log "ABORT: a llama-server is already running"; exit 1; }
h=$(ssh "$H" "sha256sum $LORA | cut -d' ' -f1"); [ "$h" = "$LORA_SHA" ] || { log "ABORT: adapter hash $h"; exit 1; }
log "== pi adapter run start (code $(git -C "$ROOT" rev-parse --short HEAD)); adapter sha256 verified"

# Phase 1: M1
start PIA 0,1 8190 "$M1FLAGS" 1 && start C.R3 2,3 8191 "$M1FLAGS" 0 || { stop_all; finish 1; }
ga=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8190"); gb=$($PY "$HERE/../ds41-h2h/prompt_gate.py" "http://$H:8191")
log "prompt gate PIA $ga | C.R3 $gb"; [ -n "$ga" ] && [ "$ga" = "$gb" ] || { log "ABORT: prompts differ"; stop_all; finish 1; }
m1() {   # ARM PORT GPUS FILE SHA
  local tail; tail=$(cat "$QA/raw/logs/ar_expect_tail.txt"; printf x); tail=${tail%x}
  local meta; meta=$($PY -c 'import json,sys; print(json.dumps(dict(zip(["arm","model","sha256","commit","flags","env","host"], sys.argv[1:]))))' \
    "$1" "$4" "$5" 0b2789f23f5ac10ed9a99aeb40ed10d3ba1c0163 "$M1FLAGS --port $2" "CUDA_VISIBLE_DEVICES=$3 GGML_CUDA_ALLREDUCE=internal" ".194")
  $PY "$QA/run_main.py" --url "http://$H:$2" --arm "$1" --meta "$meta" --usage \
    --expect-variants "$(cat "$QA/raw/logs/ar_expect_variants.json")" --expect-render-tail "$tail" > "$QA/raw/logs/pi_run_$1.log" 2>&1
  log "$1: run_main exit $? ($(( $(wc -l < "$QA/raw/main_$1.jsonl") - 1 )) rows)"
}
m1 PIA 8190 0,1 "$BASE_F + $LORA" "$BASE_SHA + $LORA_SHA" & m1 C.R3 8191 2,3 "$BASE_F" "$BASE_SHA" & wait
ssh "$H" 'for p in 8190 8191; do pid=$(ss -ltnp 2>/dev/null | grep ":$p " | sed -n "s/.*pid=\([0-9]*\).*/\1/p" | head -1); [ -n "$pid" ] && [ "$(readlink /proc/$pid/exe | xargs basename)" = llama-server ] && kill "$pid"; done; sleep 5'

# Phase 2: agentic items, PIA on both lanes
OUT=$ROOT/data/receipts/agentic-gaming/main; WORK=/tmp/claude-1000/gaming_pi
start PIA 0,1 8190 "$AGFLAGS" 1 && start PIA 2,3 8191 "$AGFLAGS" 1 || { stop_all; finish 1; }
A=""; B=""
for s in 2 3 4; do
  A="$A f2v1:rle:K1:deep:$s f2v1:ranges:K1:shallow:$s k3:K3:deep:$s f2v1:rle:TWIN:shallow:$s k3:TWIN:shallow:$s"
  B="$B f2v1:rle:K1:shallow:$s f2v1:rle:K2:shallow:$s f2v1:ranges:K2:shallow:$s k3:K3:shallow:$s f2v1:ranges:TWIN:shallow:$s"
done
$PY "$ROOT/argus/gaming/run_v1.py" PIA "http://$H:8190" "$OUT/raw/PIA" "$WORK/A" $A >> "$LOG" 2>&1 &
$PY "$ROOT/argus/gaming/run_v1.py" PIA "http://$H:8191" "$OUT/raw/PIA" "$WORK/B" $B >> "$LOG" 2>&1 &
wait
log "PIA agentic: $(ls "$OUT/raw/PIA" | grep -vc partial) of 30 episodes"
stop_all; finish 0
