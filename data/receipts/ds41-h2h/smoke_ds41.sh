#!/usr/bin/env bash
# Smoke test, one build at a time on .194 (all four P100s): does it load on upstream b12063, how much VRAM per card, and
# how fast does it decode on fresh text. Procedure only: neutral prompts, no instrument items. Writes its own PID first.
# Placement (the same for both builds, so it is not a variable): routed experts of 12 layers on the GPUs under -sm layer's
# 10-layers-per-card split: 0-1 on CUDA0 (it also holds the embeddings and the HC pre step, and ran out of memory at three
# layers on the first request, 11-03), 10-12, 20-22, 30-33 on CUDA3. The other 28 layers' experts (~93 GB) on the CPU.
# Usage (on .194): smoke_ds41.sh gsq|unsloth    -> ~/AI/Models/ds41/smoke_<build>.{log,json}
echo $$ > /tmp/smoke_ds41.pid
set -u
B=$1 D=~/AI/Models/ds41 PORT=8190
CPU_LAYERS="2|3|4|5|6|7|8|9|13|14|15|16|17|18|19|23|24|25|26|27|28|29|34|35|36|37|38|39"
OT="blk\.($CPU_LAYERS)\.ffn_(up|down|gate)_exps=CPU"
BIN=~/llama.cpp-b12063/build_sm60/bin/llama-server
case $B in
  gsq) M=$D/gsq/DeepSeek-V4.1-Flash-1017-GSQ-RCO-IQ2_XXS-00001-of-00006.gguf ;;
  unsloth) M=$D/unsloth/DeepSeek-V4.1-Flash-1017-UD-IQ1_M-00001-of-00005.gguf ;;
esac
OUT=$D/smoke_${B}; : > $OUT.json; : > $OUT.log
export GGML_CUDA_ALLREDUCE=internal   # inert on sm_60, but unset means NCCL, which aborts on .194
t0=$(date +%s)
$BIN -m $M -ngl 99 -ot "$OT" -sm layer -c 4096 -ctk f16 -ctv f16 -np 1 -fit off --cache-ram 0 --numa distribute \
  --reasoning off --host 127.0.0.1 --port $PORT > $OUT.server.log 2>&1 &   # its own file: two writers clobber
S=$!; echo $S > /tmp/smoke_ds41.server.pid
trap 'kill $S 2>/dev/null; wait $S 2>/dev/null' EXIT
until curl -sf localhost:$PORT/health > /dev/null; do
  [ -d /proc/$S ] || { echo "SERVER DIED during load after $(( $(date +%s) - t0 )) s" >> $OUT.log; exit 1; }
  sleep 5
done
echo "LOADED in $(( $(date +%s) - t0 )) s" >> $OUT.log
nvidia-smi --query-gpu=index,memory.used,memory.total --format=csv,noheader >> $OUT.log
free -g | sed -n 2p >> $OUT.log
# three fresh prompts (unseen text: PLE rows fault in on first use), greedy, every sampler explicit
for q in "Describe how a tide pool changes over one day, in about 150 words." \
         "Write a short story opening about a lighthouse keeper who collects broken clocks." \
         "Explain why bread goes stale, step by step, for a curious ten-year-old."; do
  curl -s localhost:$PORT/v1/chat/completions -H 'Content-Type: application/json' -d "$(python3 -c '
import json, sys
print(json.dumps({"messages": [{"role": "user", "content": sys.argv[1]}], "max_tokens": 160, "temperature": 0,
                  "top_p": 1.0, "top_k": 0, "min_p": 0.0, "cache_prompt": False}))' "$q")" >> $OUT.json
  echo >> $OUT.json
done
echo "SMOKE DONE" >> $OUT.log
