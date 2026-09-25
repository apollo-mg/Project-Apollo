#!/usr/bin/env bash
# Runs ON .194: two testers in parallel (GPUs 0,1 = Q6_K on :8094; GPUs 2,3 = UD-IQ3_XXS on :8095), then stops both.
set -u
cd ~/marker
BIN=~/buun-llama-cpp/build_sm60_0920/bin/llama-server     # buun 08826ad6e
FLAGS="-ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm tensor --jinja --host 0.0.0.0"
start () {   # gpus model port tag
  CUDA_VISIBLE_DEVICES=$1 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN -m "$2" $FLAGS --port $3 > server_$4.log 2>&1 < /dev/null &
  echo $! > server_$4.pid
}
start 0,1 ~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf 8094 q6k
start 2,3 ~/AI/Models/ladder_ud/Qwen3.8-27B-UD-IQ3_XXS.gguf 8095 iq3
for port in 8094 8095; do
  for i in $(seq 120); do curl -sf localhost:$port/health >/dev/null && break; sleep 5; done
  curl -sf localhost:$port/health >/dev/null || { echo "ABORT: server on $port never healthy"; exit 1; }
done
echo "## both servers up $(date -Is) $(nvidia-smi --query-gpu=clocks.sm,power.limit --format=csv,noheader | head -1)"
./marker_run.sh http://127.0.0.1:8094 out_q6k > run_q6k.log 2>&1 &
P1=$!
./marker_run.sh http://127.0.0.1:8095 out_iq3 > run_iq3.log 2>&1 &
P2=$!
wait $P1 $P2
tail -1 run_q6k.log run_iq3.log
kill "$(cat server_q6k.pid)" "$(cat server_iq3.pid)"
echo "######## MARKER DONE $(date -Is)"
