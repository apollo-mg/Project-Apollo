#!/usr/bin/env bash
# Can Flash-Next run on THREE P100s? Asked by buun 2026-09-14 after being given model-buffer
# numbers when the binding figure is the runtime total.
#
# PREDICTIONS, committed with this script before it runs:
#   P1  Q2_K_XL, 3 cards, -ngl 99, no spill  -> FAILS. Runtime needs 50,008 MiB of 49,152 available,
#       and the per-card average alone (16,669) exceeds the 16,384 limit.
#   P2  Q2_K_XL, 3 cards, -ncmoe 1           -> LOADS (frees ~1,193 MiB), decode within 10% of 4-card.
#   P3  IQ4_XS,  3 cards, -ncmoe 13          -> LOADS, decode 13.5-16.5 tok/s. This tests the ~15 tok/s
#       figure quoted to buun, which was interpolated between ladder rungs 8 (17.60) and 16 (13.57),
#       never measured.
# Decode: /completion, n_predict 128, ignore_eos, 3 reps, median of the server's own timings --
# the same shape as RESULT_SPLITMODE_SWEEP_27B.md so the arms here are comparable to each other.
set -u
W=~/threecard; mkdir -p "$W"; L=$W/run.log; R=$W/rows.jsonl
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
Q2=~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
IQ4=~/AI/Models/flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf
PORT=8115
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server already running"; exit 1; }

arm () {   # label model devices extra_flags...
  local lab=$1 model=$2 dev=$3; shift 3
  local log=$W/s_$lab.log
  say "=== $lab  devices=$dev  flags: $*"
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=$dev \
    "$BIN" -m "$model" -ngl 99 --numa distribute -c 2048 -np 1 -fa on \
           -ctk f16 -ctv f16 -sm layer -fit off "$@" \
           --host 127.0.0.1 --port $PORT > "$log" 2>&1 &
  local pid=$! ok=0
  for i in $(seq 1 900); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    say "$lab: DID NOT LOAD"
    grep -iE "out of memory|failed to allocate|cudaMalloc|error|abort" "$log" | tail -4 | sed 's/^/    /' | tee -a "$L"
    echo "{\"arm\":\"$lab\",\"loaded\":false}" >> "$R"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    for i in $(seq 1 90); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break; sleep 1; done
    return
  fi
  local vram; vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/')
  python3 -u - "$PORT" "$lab" "$dev" "$vram" "$R" <<'PY' 2>&1 | tee -a "$L"
import json, statistics, sys, urllib.request
port, lab, dev, vram, rows = sys.argv[1:6]
def post(p, b, t=900):
    r = urllib.request.Request(f"http://127.0.0.1:{port}{p}", data=json.dumps(b).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=t))
m = post("/v1/chat/completions", {"messages":[{"role":"user","content":"What is 17 * 23? Reply with only the number."}],
         "max_tokens":32,"temperature":0,"chat_template_kwargs":{"enable_thinking":False}})["choices"][0]["message"]
said = ((m.get("content") or "")+(m.get("reasoning_content") or "")).strip()
prompt = "The history of scientific instruments is"
post("/completion", {"prompt":prompt,"n_predict":8,"cache_prompt":False,"temperature":0})
tg = []
for _ in range(3):
    t = post("/completion", {"prompt":prompt,"n_predict":128,"cache_prompt":False,
                             "temperature":0,"ignore_eos":True}).get("timings",{})
    tg.append(t.get("predicted_per_second") or 0.0)
row = {"arm":lab,"devices":dev,"vram":vram,"loaded":True,"coherent":"391" in said,
       "tg_tps":round(statistics.median(tg),2),"tg_all":[round(x,2) for x in tg]}
open(rows,"a").write(json.dumps(row)+"\n")
print(f"    LOADED. decode {row['tg_tps']:.2f} tok/s {row['tg_all']}  VRAM {vram}  coherent={row['coherent']}")
PY
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 120); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break; sleep 1; done
}

arm Q2-3card-nospill "$Q2"  0,1,2
arm Q2-3card-ncmoe1  "$Q2"  0,1,2   -ncmoe 1
arm Q2-4card-ref     "$Q2"  0,1,2,3
arm IQ4-3card-ncmoe13 "$IQ4" 0,1,2  -ncmoe 13
say "=== THREECARD COMPLETE ==="
