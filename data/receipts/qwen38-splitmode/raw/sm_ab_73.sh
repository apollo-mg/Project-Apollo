#!/usr/bin/env bash
# -sm layer vs -sm tensor on 2x P100, Qwen 3.8 27B dense.
#
# buun_vbr documents tensor as "split weights and KV across GPUs (parallelized)",
# against layer's "split layers and KV across GPUs (pipelined)". Pipelined layer
# split means only one card computes at a time on a single sequence; tensor split
# parallelises within each op. On 2 cards that is the difference between using one
# GPU's compute and using both.
#
# qwen35 is NOT on buun_vbr's llm_arch_supports_sm_tensor denylist (DEEPSEEK4 and
# NEMOTRON_H_MOE are), so this loads. Verified before launch.
#
# MTP OFF in every arm: speculative decoding changes batch shape, which is exactly
# what a split-mode comparison must hold constant.
set -u
SP=/home/mark/mtp73
BIN=/home/mark/buun_vbr/build/bin/llama-server
M=/home/mark/models/Qwen3.8-27B-UD-IQ3_XXS.gguf
export LD_LIBRARY_PATH="$(dirname $BIN):${LD_LIBRARY_PATH:-}"
export REPS=2

serve () {
  pgrep -x llama-server >/dev/null && { pkill -x llama-server; sleep 6; }
  setsid nohup "$BIN" -m "$M" -ngl 999 -c 8192 -fa on -np 1 $1 \
      --port 8082 --host 127.0.0.1 > "$SP/srv_sm.log" 2>&1 < /dev/null &
  for i in $(seq 1 150); do
    curl -s http://127.0.0.1:8082/health 2>/dev/null | grep -q '"ok"' && return 0
    sleep 5
  done
  echo "  SERVER FAILED"; grep -aiE "error|not implemented" "$SP/srv_sm.log" | head -3; return 1
}

nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader

echo "### A: -sm layer -ts 1,1"
serve "-sm layer -ts 1,1" && python3 $SP/mtp_ab.py smlayer_1
echo "### B: -sm tensor"
serve "-sm tensor"        && python3 $SP/mtp_ab.py smtensor_1
echo "### C: -sm tensor (repeat)"
serve "-sm tensor"        && python3 $SP/mtp_ab.py smtensor_2
echo "### D: -sm layer -ts 1,1 (repeat)"
serve "-sm layer -ts 1,1" && python3 $SP/mtp_ab.py smlayer_2
pkill -x llama-server 2>/dev/null
echo "### SM AB DONE"
