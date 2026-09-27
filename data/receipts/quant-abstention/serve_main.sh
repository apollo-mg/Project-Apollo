#!/usr/bin/env bash
# Start one main-campaign arm on one lane of .194 (PREREG_MAIN.md). Lane A = GPUs 0,1 on :8190, lane B = GPUs 2,3 on
# :8191. Same build and flags as the pilot (buun 0b2789f23 sm_60, f16 KV explicit, -np 1, -lv 4). Restarts that
# lane's previous server by its recorded PID. Writes ~/qa_main_meta_<arm>.json (model, lane, devices, commit, clocks,
# the log lines that prove the KV type and MTP state).
# usage: serve_main.sh LANE ARM MODEL_PATH SHA256
set -uo pipefail
LANE=$1; ARM=$2; MODEL=$3; SHA=$4
case "$LANE" in A) DEVS=0,1; PORT=8190 ;; B) DEVS=2,3; PORT=8191 ;; *) echo "bad lane"; exit 2 ;; esac
BIN=~/buun-0b278/build_sm60/bin/llama-server
LOG=~/qa_main_server_$ARM.log; PID=~/qa_main_server_$LANE.pid
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port $PORT"
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  kill "$(cat "$PID")"; while kill -0 "$(cat "$PID")" 2>/dev/null; do sleep 1; done
fi
# EXL3 import stages tensors next to the model or in $LLAMA_CACHE: keep it on this lane's own scratch
mkdir -p ~/qa_stage/cache_$LANE
LLAMA_CACHE=~/qa_stage/cache_$LANE CUDA_VISIBLE_DEVICES=$DEVS GGML_CUDA_ALLREDUCE=internal \
  nohup "$BIN" -m "$MODEL" $FLAGS > "$LOG" 2>&1 < /dev/null &
echo $! > "$PID"
for i in $(seq 1 450); do
  curl -sf "localhost:$PORT/health" >/dev/null && break
  kill -0 "$(cat "$PID")" 2>/dev/null || { echo "server died"; tail -n 20 "$LOG"; exit 1; }
  sleep 2
done
curl -sf "localhost:$PORT/health" >/dev/null || { echo "not healthy"; tail -n 20 "$LOG"; exit 1; }
python3 - "$ARM" "$MODEL" "$SHA" "$FLAGS" "$LOG" "$LANE" "$DEVS" <<'EOF' > ~/qa_main_meta_$2.json
import json, os, re, subprocess, sys
arm, model, sha, flags, log, lane, devs = sys.argv[1:]
lines = open(log, errors="replace").read().splitlines()
pat = r"K \(|V \(|kv_cache: size|mtp|MTP|draft|nextn|n_ctx_slot|safetensors|exl3|EXL3"
keep = [re.sub(r"/home/[a-z]+", "~", l)[:200] for l in lines if re.search(pat, l) and "llama_model_loader" not in l]
kv_f16 = any("K (f16)" in l and "V (f16)" in l for l in lines)
mtp_active = any(re.search(r"(draft|mtp).*(context|init|loaded|enabled)", l, re.I) and "unused" not in l for l in lines)
smi = subprocess.run(["nvidia-smi", "--query-gpu=index,clocks.sm,clocks.mem,power.limit,memory.used",
                      "--format=csv,noheader"], capture_output=True, text=True).stdout.strip().splitlines()
commit = subprocess.run(["git", "-C", os.path.expanduser("~/buun-0b278"), "rev-parse", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
print(json.dumps({"arm": arm, "lane": lane, "devices": devs, "model": re.sub(r"/home/[a-z]+", "~", model),
                  "sha256": sha, "commit": commit, "flags": flags,
                  "env": f"CUDA_VISIBLE_DEVICES={devs} GGML_CUDA_ALLREDUCE=internal",
                  "kv_f16_verified": kv_f16, "mtp_or_draft_line_seen": mtp_active,
                  "nvidia_smi": smi, "log_lines": keep[:80]}))
EOF
echo "ok $ARM $LANE"
