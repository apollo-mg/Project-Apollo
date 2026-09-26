#!/usr/bin/env bash
# Start one pilot arm on .194 (PREREG_PILOT.md, one instrument): buun 0b2789f23 sm_60, GPUs 0+1, -sm layer,
# f16 KV passed explicitly (buun defaults to VBR), -np 1, no draft/MTP flags. Restarts any previous arm by its
# recorded PID. Writes ~/qa_meta_<arm>.json: model path + sha256, commit, flags, GPU clocks, and the server-log
# lines that prove the KV type and the device split.
# usage: serve_arm.sh ARM MODEL_PATH [PORT]
set -uo pipefail
ARM=$1; MODEL=$2; PORT=${3:-8190}
BIN=~/buun-0b278/build_sm60/bin/llama-server
LOG=~/qa_pilot_server_$ARM.log; PID=~/qa_pilot_server.pid
FLAGS="-ngl 99 -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --host 0.0.0.0 --port $PORT"
if [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  kill "$(cat "$PID")"; while kill -0 "$(cat "$PID")" 2>/dev/null; do sleep 1; done
fi
CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal nohup "$BIN" -m "$MODEL" $FLAGS > "$LOG" 2>&1 < /dev/null &
echo $! > "$PID"
for i in $(seq 1 240); do
  curl -sf "localhost:$PORT/health" >/dev/null && break
  kill -0 "$(cat "$PID")" 2>/dev/null || { echo "server died"; tail -n 20 "$LOG"; exit 1; }
  sleep 2
done
curl -sf "localhost:$PORT/health" >/dev/null || { echo "not healthy"; tail -n 20 "$LOG"; exit 1; }
SHA=$(grep -F "$MODEL" ~/qa_sha_194.txt | cut -d' ' -f1)
python3 - "$ARM" "$MODEL" "$SHA" "$FLAGS" "$LOG" <<'EOF' > ~/qa_meta_$1.json
import json, re, subprocess, sys
arm, model, sha, flags, log = sys.argv[1:]
lines = open(log, errors="replace").read().splitlines()
keep = [re.sub(r"/home/[a-z]+", "~", l)[:200] for l in lines if re.search(r"type_k|type_v|K \(|V \(|kv_cache|KV self size|mtp|MTP|draft|nextn|n_ctx|offloaded|CUDA[01]|splitting|split_mode|Device [0-9]", l)]
smi = subprocess.run(["nvidia-smi", "--query-gpu=index,clocks.sm,clocks.mem,power.limit,memory.used",
                      "--format=csv,noheader"], capture_output=True, text=True).stdout.strip().splitlines()
import os
commit = subprocess.run(["git", "-C", os.path.expanduser("~/buun-0b278"), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
print(json.dumps({"arm": arm, "model": re.sub(r"/home/[a-z]+", "~", model), "sha256": sha, "commit": commit,
                  "flags": flags, "env": "CUDA_VISIBLE_DEVICES=0,1 GGML_CUDA_ALLREDUCE=internal",
                  "nvidia_smi": smi, "log_lines": keep[:60]}))
EOF
echo "ok $ARM"
