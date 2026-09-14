#!/usr/bin/env bash
# Matched-footprint pelicans: EXL3 3.05bpw (50,060 MiB) vs UD-Q2_K_XL (50,190 MiB) -- 130 MiB apart.
# Settings identical to the thinking-ON matched run (fair2) so all three arms are comparable:
#   -c 24576 --kv-unified -ctk q8_0 -ctv q8_0 --reasoning-effort medium --min-p 0 --jinja -lv 4
#   temperature 1.0, max_tokens 8000, 3 reps, PASS 1 ONLY.
# The third arm (UD-IQ4_XS -ncmoe 2, 61,566 MiB) is already measured in fair2/.
#
# Declared deviations:
#  - EXL3's manifest is NOT re-verified here (it took 1,133 s on 09-13 and the files have not moved).
#    Provenance rests on that verification.
#  - EXL3 stages a ~31 GB temp file during load; .194 has 61 GB free. This is the ENOSPC that killed
#    Stage 2 once, so free space is checked before the arm runs and the arm aborts rather than filling
#    the disk.
set -u
W=~/matched3; mkdir -p "$W"; L=$W/run.log
BIN=~/buun-c7f114d34/build_sm60/bin/llama-server
Q2=~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf
EXL3=~/AI/Models/exl3/Qwen3.8-Flash-Next-exl3-3.05bpw_h5_ng5
PORT=8119
say () { echo "$(date '+%F %T') $*" | tee -a "$L"; }
pgrep -x llama-server >/dev/null && { say "ABORT: llama-server running"; exit 1; }

arm () {   # label model_path extra_flags...
  local lab=$1 model=$2; shift 2
  say "=== $lab"
  if [ "$lab" = "EXL3" ]; then
    FREE=$(df --output=avail -BG ~ | tail -1 | tr -dc '0-9')
    say "    free space ${FREE} GB (needs ~31 GB for safetensors staging)"
    [ "$FREE" -lt 40 ] && { say "    ABORT arm: under 40 GB free, refusing to risk ENOSPC"; return; }
  fi
  local T0=$(date +%s)
  GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3 \
    "$BIN" -m "$model" -ngl 99 --numa distribute -c 24576 -np 1 -fa on --kv-unified \
           -ctk q8_0 -ctv q8_0 -sm layer -fit off --reasoning-effort medium --min-p 0 \
           --jinja -lv 4 -lm dio "$@" --host 127.0.0.1 --port $PORT > "$W/s_$lab.log" 2>&1 &
  local pid=$! ok=0
  for i in $(seq 1 1800); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && { ok=1; break; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$ok" != 1 ]; then
    say "    DID NOT LOAD after $(( $(date +%s)-T0 ))s"
    grep -iE "error|abort|no space|out of memory" "$W/s_$lab.log" | tail -4 | sed 's/^/    /' | tee -a "$L"
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null; return
  fi
  say "    up in $(( $(date +%s)-T0 ))s | VRAM $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr '\n' '/')"
  python3 -u - "$PORT" "$W" "$lab" <<'PY' 2>&1 | tee -a "$L"
import json,re,sys,time,urllib.request
port,W,lab=sys.argv[1],sys.argv[2],sys.argv[3]
TASK="Generate an SVG of a pelican riding a bicycle."
for r in (1,2,3):
    body=json.dumps({"messages":[{"role":"user","content":TASK}],"max_tokens":8000,
                     "temperature":1.0,"min_p":0.0}).encode()
    q=urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",data=body,
                             headers={"Content-Type":"application/json"})
    t0=time.time(); d=json.load(urllib.request.urlopen(q,timeout=2400)); dt=time.time()-t0
    m=d["choices"][0]["message"]; txt=m.get("content") or ""; think=m.get("reasoning_content") or ""
    n=d.get("usage",{}).get("completion_tokens",0)
    open(f"{W}/{lab}_rep{r}.content.txt","w").write(txt)
    s=re.findall(r"<svg\b.*?</svg>",txt,re.S|re.I)
    if s: open(f"{W}/{lab}_rep{r}.svg","w").write(s[0])
    print(f"    {lab} rep{r}: {n} tok in {dt:.0f}s = {n/dt:.1f} tok/s | svg={'YES' if s else 'NO'} | reasoning {len(think)} chars")
PY
  kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
  for i in $(seq 1 150); do
    [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | sort -n | tail -1)" -lt 500 ] && break
    sleep 1
  done
}

arm Q2K "$Q2"
arm EXL3 "$EXL3"
say "=== MATCHED3 COMPLETE ==="
