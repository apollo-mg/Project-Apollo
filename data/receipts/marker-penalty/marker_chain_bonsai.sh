#!/usr/bin/env bash
# Runs ON .194. PREREG_MARKER_PENALTY_BONSAI.md: Bonsai 2 PQ2_0 on the prism fork, items split across two 2-GPU testers.
# Separate output dirs per tester (out_bonsai1/2): rows exceed PIPE_BUF, so concurrent appends to one file could interleave.
set -u
cd ~/marker
BIN=~/prism_llama_cpp/build_sm60/bin/llama-server
M=~/AI/Models/ladder/Ternary-Bonsai-2-27B-PQ2_0.gguf
FLAGS="-ngl 99 -c 16384 -np 1 -fa on --kv-unified -ctk f16 -ctv f16 -sm layer --jinja --host 0.0.0.0"   # Deviation 1: prism aborts under -sm tensor
{ echo "## RUNLOG $(date -Is)"; echo "binary $BIN commit $(cd ~/prism_llama_cpp && git rev-parse HEAD)"
  echo "model $M bytes $(stat -c %s $M) sha256 $(sha256sum $M | cut -c1-64)"; } > RUNLOG_bonsai.txt
start () {   # gpus port tag
  CUDA_VISIBLE_DEVICES=$1 GGML_CUDA_ALLREDUCE=internal setsid nohup $BIN -m "$M" $FLAGS --port $2 > server_$3.log 2>&1 < /dev/null &
  echo $! > server_$3.pid
}
start 0,1 8096 bon1
start 2,3 8097 bon2
for port in 8096 8097; do
  for i in $(seq 120); do curl -sf localhost:$port/health >/dev/null && break; sleep 5; done
  curl -sf localhost:$port/health >/dev/null || { echo "ABORT: server on $port never healthy"; exit 1; }
done
echo "## both servers up $(date -Is) $(nvidia-smi --query-gpu=clocks.sm,power.limit --format=csv,noheader | head -1)" | tee -a RUNLOG_bonsai.txt
ITEMS="CAL-A1 CAL-A2 CAL-A3 CAL-A4 CAL-U1 CAL-U2 CAL-U3 CAL-U4" ./marker_run.sh http://127.0.0.1:8096 out_bonsai1 > run_bon1.log 2>&1 &
P1=$!
ITEMS="CAL-A5 CAL-A6 CAL-A7 CAL-A8 CAL-U5 CAL-U6 CAL-U7 CAL-U8" ./marker_run.sh http://127.0.0.1:8097 out_bonsai2 > run_bon2.log 2>&1 &
P2=$!
wait $P1 $P2
kill "$(cat server_bon1.pid)" "$(cat server_bon2.pid)"
echo "######## BONSAI DONE $(date -Is)"
