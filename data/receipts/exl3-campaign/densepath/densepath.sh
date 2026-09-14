#!/usr/bin/env bash
# PREREG_SM60_DENSE_PATH.md -- does dense GGUF peak VRAM grow with -ub (dequant-pool signature)
# while EXL3 stays flat (256 MB bounded chunks)? Two P100s, matching the node shape of the
# original OOM. An arm that fails to load is a RESULT, recorded, not retried.
set -u
W=~/densepath; mkdir -p "$W"; L=$W/run.log; R=$W/rows.jsonl
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
Q6=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
X3=~/AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw
PORT=8120
say(){ echo "$(date '+%F %T') $*" | tee -a "$L"; }
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server running"; exit 1; }

arm(){  # label model ub
  local lab="$1" model="$2" ub="$3"
  local log="$W/s_${lab}.log"
  say "=== $lab  (-ub $ub)"
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1 \
    "$BIN" -m "$model" -ngl 99 -sm layer -fit off -c 4096 -b 2048 -ub "$ub" -np 1 \
           -fa on -ctk f16 -ctv f16 --host 127.0.0.1 --port $PORT > "$log" 2>&1 &
  local pid=$! ok=0
  for i in $(seq 1 600); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    local why
    why=$(grep -oiE "out of memory|failed to allocate[^\"]*|cudaMalloc failed[^\"]*" "$log" | tail -1)
    say "    DID NOT LOAD -- ${why:-unknown}"
    echo "{\"arm\":\"$lab\",\"ub\":$ub,\"loaded\":false,\"why\":\"${why:-unknown}\"}" >> "$R"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    for i in $(seq 1 90); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits|sort -n|tail -1)" -lt 500 ] && break; sleep 1; done
    return
  fi
  # sample peak VRAM across both cards while the prefill runs
  ( while :; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | paste -sd+ | bc; sleep 2; done ) > "$W/peak_$lab.txt" &
  local sampler=$!
  python3 -u - "$PORT" "$W" "$lab" "$ub" <<'PY' 2>&1 | tee -a "$L"
import json,sys,urllib.request
port,W,lab,ub=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
def post(p,b,t=900):
    r=urllib.request.Request(f"http://127.0.0.1:{port}{p}",data=json.dumps(b).encode(),
                             headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(r,timeout=t))
txt=open("/mnt/HDD/exl3/wiki.test.raw",encoding="utf-8").read()[:40000]
ids=post("/tokenize",{"content":txt})["tokens"][:2048]
post("/completion",{"prompt":ids[:64],"n_predict":4,"cache_prompt":False,"temperature":0})
pp=[]
for _ in range(3):
    t=post("/completion",{"prompt":ids,"n_predict":8,"cache_prompt":False,"temperature":0}).get("timings",{})
    pp.append(t.get("prompt_per_second") or 0.0)
pp.sort()
open(f"{W}/pp_{lab}.txt","w").write(str(pp[1]))
print(f"    prefill {pp[1]:.1f} tok/s over {len(ids)} tokens  (reps {[round(x,1) for x in pp]})")
PY
  kill "$sampler" 2>/dev/null
  local peak; peak=$(sort -n "$W/peak_$lab.txt" 2>/dev/null | tail -1)
  local pps;  pps=$(cat "$W/pp_$lab.txt" 2>/dev/null)
  say "    peak VRAM ${peak} MiB"
  echo "{\"arm\":\"$lab\",\"ub\":$ub,\"loaded\":true,\"peak_mib\":${peak:-0},\"pp_tps\":${pps:-0}}" >> "$R"
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 120); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits|sort -n|tail -1)" -lt 500 ] && break; sleep 1; done
}

for ub in 8 64 128 256 512; do arm "Q6K-ub$ub" "$Q6" "$ub"; done
for ub in 8 64 128 256 512; do arm "EXL3-ub$ub" "$X3" "$ub"; done
say "=== DENSEPATH COMPLETE ==="
