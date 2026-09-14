#!/usr/bin/env bash
# 27B dense speed sweep on .194, c7f114d34: split mode x device count, with timings.
# Prompted by buun: "a lot more work was put into -sm tensor during the safetensors work".
# Existing numbers are .73 / 2 cards / 9ae8f0f40 (Q6_K layer 7.81 -> tensor 13.22). This is a NEW
# baseline on .194 / 4 cards / IQ3_XXS -- the comparable quantity is the within-sweep ratio, not
# a cross-node delta.
# 1 device is included deliberately: it is what makes "layer split is inert" falsifiable.
set -u
W=~/sweep27b; mkdir -p "$W"; L=$W/sweep.log; R=$W/rows.jsonl
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
M=~/AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf
PORT=8113
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }
[ -f "$M" ] || { say "ABORT: no model"; exit 1; }
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server already running"; exit 1; }

arm () {   # label devices splitmode
  local lab=$1 dev=$2 sm=$3 log=$W/s_$1.log
  say "=== $lab  (devices=$dev, -sm $sm)"
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=$dev \
    "$BIN" -m "$M" -ngl 99 -c 2048 -np 1 -fa on -ctk f16 -ctv f16 -sm "$sm" -fit off \
           --host 127.0.0.1 --port $PORT > "$log" 2>&1 &
  local pid=$! ok=0
  for i in $(seq 1 400); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    say "$lab: DID NOT COME UP"; tail -6 "$log" | sed 's/^/    /' | tee -a "$L"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; return
  fi
  local vram; vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/')
  python3 - "$PORT" "$lab" "$dev" "$sm" "$vram" "$R" <<'PY' 2>&1 | tee -a "$L"
import json, statistics, sys, urllib.request
port, lab, dev, sm, vram, rows = sys.argv[1:7]
def post(path, payload, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))
# coherence first -- a speed number from a broken arm is worthless
m = post("/v1/chat/completions", {"messages":[{"role":"user","content":"What is 17 * 23? Reply with only the number."}],
         "max_tokens":32,"temperature":0,"chat_template_kwargs":{"enable_thinking":False}})["choices"][0]["message"]
said = ((m.get("content") or "")+(m.get("reasoning_content") or "")).strip()
coherent = "391" in said
prompt = "The history of scientific instruments is"
post("/completion", {"prompt":prompt,"n_predict":8,"cache_prompt":False,"temperature":0})  # warm
tg, pp = [], []
for _ in range(3):
    t = post("/completion", {"prompt":prompt,"n_predict":128,"cache_prompt":False,
                             "temperature":0,"ignore_eos":True}).get("timings",{})
    tg.append(t.get("predicted_per_second") or 0.0); pp.append(t.get("prompt_per_second") or 0.0)
row = {"arm":lab,"devices":dev,"sm":sm,"vram":vram,"coherent":coherent,"said":said[:40],
       "tg_tps":round(statistics.median(tg),2),"tg_all":[round(x,2) for x in tg],
       "pp_tps":round(statistics.median(pp),1)}
open(rows,"a").write(json.dumps(row)+"\n")
flag = "" if coherent else "   <-- INCOHERENT, speed not meaningful"
print(f"    decode {row['tg_tps']:.2f} tok/s  (reps {row['tg_all']})   VRAM {vram}{flag}")
PY
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 120); do
    [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break
    sleep 1
  done
}

arm S-1dev      0       layer      # single card: the reference layer split must beat to be useful
arm L-2dev      0,1     layer
arm L-3dev      0,1,2   layer
arm L-4dev      0,1,2,3 layer
arm T-2dev      0,1     tensor
arm T-3dev      0,1,2   tensor
arm T-4dev      0,1,2,3 tensor
say "=== SWEEP 27B COMPLETE ==="
