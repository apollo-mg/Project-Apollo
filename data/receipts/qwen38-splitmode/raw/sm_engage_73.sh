#!/usr/bin/env bash
# Engagement probe for -sm layer vs -sm tensor on 2x P100.
#
# The A/B log cannot prove -sm tensor engaged: every arm overwrote a single
# srv_sm.log, and this build does not print a split-mode line at all. So prove
# it from the mechanism instead. buun_vbr documents layer as "pipelined" and
# tensor as "parallelized": on ONE sequence, a pipelined layer split can only
# have one card computing at a time, while a tensor split has both working on
# every op. Sampling utilisation during generation separates those directly.
set -u
D=/home/mark/mtp73
BIN=/home/mark/buun_vbr/build/bin/llama-server
M=/home/mark/models/Qwen3.8-27B-UD-IQ3_XXS.gguf
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"

probe () {          # $1 = tag, $2 = split flags
  local tag=$1 flags=$2
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 6; }
  setsid nohup "$BIN" -m "$M" -ngl 999 -c 8192 -fa on -np 1 $flags \
      --port 8082 --host 127.0.0.1 > "$D/eng_${tag}.log" 2>&1 < /dev/null &
  for i in $(seq 1 150); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && break
    sleep 5
  done
  curl -s http://127.0.0.1:8082/health | grep -q '"ok"' || { echo "$tag: SERVER FAILED"; return 1; }

  echo "--- $tag resident VRAM (MiB) ---"
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader

  # fire a long generation, sample utilisation while it runs
  curl -s http://127.0.0.1:8082/v1/chat/completions -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Write the numbers 1 to 200, one per line."}],
         "temperature":0,"top_k":1,"seed":1234,"n_predict":300}' > "$D/eng_${tag}.json" 2>&1 &
  local cpid=$!
  sleep 4                       # skip prompt-processing, sample steady-state decode
  : > "$D/util_${tag}.csv"
  for i in $(seq 1 60); do
    nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits \
      | paste -sd' ' >> "$D/util_${tag}.csv"
    sleep 0.3
  done
  wait $cpid
  pkill -x llama-server; sleep 5
}

nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader
probe layer  "-sm layer -ts 1,1"
probe tensor "-sm tensor"
echo "### ENGAGE PROBE DONE"
