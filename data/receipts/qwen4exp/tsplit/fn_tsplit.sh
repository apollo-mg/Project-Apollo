#!/usr/bin/env bash
# The direct reproduction: qwen4exp/Flash-Next at 4 devices, tensor vs layer, on c7f114d34.
# The 08-28 finding (c232282aa) was garbage output + 6.14 tok/s under tensor, 15.85 under layer.
# Q2_K_XL (~50 GB resident) is the only Flash-Next that fits 4x16GB fully resident at -ngl 99.
set -u
W=~/tsplit; mkdir -p "$W"; L=$W/fn.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
M=~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
PORT=8112
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }
[ -f "$M" ] || { say "ABORT: no model at $M"; exit 1; }
pgrep -x llama-server >/dev/null && { say "ABORT: a llama-server is already running"; exit 1; }

arm () {   # label splitmode
  local lab=$1 sm=$2 log=$W/fn_$1.log
  say "=== $lab: -sm $sm on 4 devices"
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3 \
    "$BIN" -m "$M" -ngl 99 -c 2048 -np 1 -fa on -ctk f16 -ctv f16 -sm "$sm" -fit off \
           --host 127.0.0.1 --port $PORT > "$log" 2>&1 &
  local pid=$! ok=0
  for i in $(seq 1 600); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    say "$lab: DID NOT COME UP. Last lines:"; tail -8 "$log" | sed 's/^/    /' | tee -a "$L"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; return
  fi
  say "$lab: VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/')"
  for q in "What is 17 * 23? Reply with only the number." "What is the capital of France? One word."; do
    curl -sf -m 300 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
      -d "$(python3 -c "
import json,sys
print(json.dumps({'messages':[{'role':'user','content':sys.argv[1]}],'max_tokens':48,'temperature':0,
                  'chat_template_kwargs':{'enable_thinking':False}}))" "$q")" \
    | python3 -c "
import json,sys
d=json.load(sys.stdin); m=d['choices'][0]['message']; u=d.get('usage',{})
t=((m.get('content') or '')+(m.get('reasoning_content') or '')).strip().replace(chr(10),' ')
print('    A:', repr(t[:110]), '| completion_tokens=', u.get('completion_tokens'))" 2>&1 | tee -a "$L"
  done
  # timed decode, same shape as the 08-28 comparison
  python3 - "$PORT" <<'PY' 2>&1 | tee -a "$L"
import json, sys, time, urllib.request
port = sys.argv[1]
body = json.dumps({"messages":[{"role":"user","content":"Write three sentences about the ocean."}],
                   "max_tokens":128,"temperature":0,
                   "chat_template_kwargs":{"enable_thinking":False}}).encode()
t0 = time.time()
r = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=body,
                           headers={"Content-Type":"application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300)); dt = time.time()-t0
n = d.get("usage",{}).get("completion_tokens",0)
m = d["choices"][0]["message"]
txt = ((m.get("content") or "")+(m.get("reasoning_content") or "")).strip().replace("\n"," ")
print(f"    decode: {n} tok in {dt:.1f}s = {n/dt:.2f} tok/s")
print(f"    text: {txt[:150]!r}")
PY
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 120); do
    [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break
    sleep 1
  done
}
arm FN-tensor4 tensor
arm FN-layer4  layer
say "=== FN TSPLIT COMPLETE ==="
