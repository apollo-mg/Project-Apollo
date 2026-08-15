#!/usr/bin/env bash
# The arm the A/B was missing: ONE P100, no split at all.
#
# Qwen3.8-27B-UD-IQ3_XXS is 11.09 GiB and the layer-split arm used ~6 GiB per
# card, so this model fits on a single 16 GiB P100. Without this cell the 1.63x
# tensor-over-layer result is unreadable: it either means tensor split is a real
# gain over the best alternative, or that layer split is a pipelining loss you
# avoid by simply not splitting. Same numbers, opposite advice.
#
# Also captures per-device model buffer sizes at -lv 5, which the A/B logs lack
# entirely (this build prints no load_tensors block at default verbosity), to
# give -sm tensor a structural engagement proof independent of throughput.
set -u
D=/home/mark/mtp73
BIN=/home/mark/buun_vbr/build/bin/llama-server
M=/home/mark/models/Qwen3.8-27B-UD-IQ3_XXS.gguf
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"
export REPS=2

serve () {   # $1 = tag (names the log), $2 = flags, $3 = extra env prefix
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 6; }
  env $3 setsid nohup "$BIN" -m "$M" -ngl 999 -c 8192 -fa on -np 1 $2 \
      --port 8082 --host 127.0.0.1 > "$D/srv_$1.log" 2>&1 < /dev/null &
  for i in $(seq 1 150); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && return 0
    sleep 5
  done
  echo "  SERVER FAILED ($1)"
  grep -aiE "error|out of memory|failed|not implemented" "$D/srv_$1.log" | head -5
  return 1
}

nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader

# --- buffer-size capture at high verbosity: the structural proof ---
for pair in "bufLAYER:-sm layer -ts 1,1" "bufTENSOR:-sm tensor"; do
  tag=${pair%%:*}; flags=${pair#*:}
  if serve "$tag" "$flags -lv 5" ""; then
    echo "### $tag buffers"
    grep -aiE "model buffer size|KV buffer size|CUDA[01] .*buffer|load_tensors" "$D/srv_$tag.log" | head -12
    nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  fi
done

# --- the missing cell ---
echo "### E: single GPU (CUDA_VISIBLE_DEVICES=0, no split)"
if serve "single_1" "" "CUDA_VISIBLE_DEVICES=0"; then
  nvidia-smi --query-gpu=index,memory.used --format=csv,noheader
  python3 $D/mtp_ab.py single_1
else
  echo "  single-GPU did not load at -c 8192 — that is itself the answer, recorded."
fi
echo "### F: single GPU repeat (fresh load)"
serve "single_2" "" "CUDA_VISIBLE_DEVICES=0" && python3 $D/mtp_ab.py single_2

pkill -x llama-server 2>/dev/null
echo "### SINGLE GPU DONE"
