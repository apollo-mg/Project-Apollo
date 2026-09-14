#!/usr/bin/env bash
# Does -sm tensor still produce garbage at >=3 devices on c7f114d34?
# The 08-28 finding (RESULT_c232282aa_VERIFY.md S6) was on qwen4exp/Flash-Next at 4 devices.
# This asks the SCOPE question: does a dense model corrupt the same way, or is it GDN-specific?
# Dense Qwen3.8-27B UD-IQ3_XXS (11.9 GB) fits on 2, 3 or 4 cards with no spill, so device count
# is the only thing that varies.
set -u
W=~/tsplit; mkdir -p "$W"; L=$W/check.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
M=~/AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf
PORT=8111
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }

[ -x "$BIN" ] || { say "ABORT: no binary at $BIN"; exit 1; }
[ -f "$M" ]   || { say "ABORT: no model at $M"; exit 1; }
pgrep -x llama-server >/dev/null && { say "ABORT: a llama-server is already running"; exit 1; }

arm () {   # label  devices  splitmode
  local lab=$1 dev=$2 sm=$3 log=$W/server_$1.log out=$W/out_$1.txt
  say "=== $lab: CUDA_VISIBLE_DEVICES=$dev -sm $sm"
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=$dev \
    "$BIN" -m "$M" -ngl 99 -c 2048 -np 1 -fa on -ctk f16 -ctv f16 -sm "$sm" -fit off \
           --host 127.0.0.1 --port $PORT > "$log" 2>&1 &
  local pid=$!
  local ok=0
  for i in $(seq 1 300); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    say "$lab: SERVER DID NOT COME UP -- tail:"; tail -5 "$log" | tee -a "$L"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; return
  fi
  local vram; vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/' )
  # three probes: arithmetic, a fact, and a greedy continuation to compare byte-for-byte across arms
  : > "$out"
  for q in "What is 17 * 23? Reply with only the number." \
           "What is the capital of France? One word." \
           "Count from 1 to 10, separated by spaces. Numbers only."; do
    r=$(curl -sf -m 240 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
        -d "$(python3 -c "
import json,sys
print(json.dumps({'messages':[{'role':'user','content':sys.argv[1]}],'max_tokens':64,
                  'temperature':0,'chat_template_kwargs':{'enable_thinking':False}}))" "$q")" \
        | python3 -c "
import json,sys
try:
    m=json.load(sys.stdin)['choices'][0]['message']
    print(((m.get('content') or '')+(m.get('reasoning_content') or '')).strip().replace(chr(10),' ')[:120])
except Exception as e:
    print('PARSE-FAIL', e)")
    echo "  Q: $q" >> "$out"; echo "  A: $r" >> "$out"
  done
  local tps; tps=$(curl -sf -m 240 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"Write one sentence about the sea."}],"max_tokens":64,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' \
      | python3 -c "import json,sys; d=json.load(sys.stdin); t=d.get('usage',{}); print(t.get('completion_tokens','?'))" 2>/dev/null)
  say "$lab: up, VRAM $vram, completion_tokens=$tps"
  sed 's/^/    /' "$out" | tee -a "$L"
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 90); do
    [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break
    sleep 1
  done
}

arm REF-layer4  0,1,2,3 layer
arm TEN-2dev    0,1     tensor
arm TEN-3dev    0,1,2   tensor
arm TEN-4dev    0,1,2,3 tensor
say "=== TSPLIT CHECK COMPLETE ==="
