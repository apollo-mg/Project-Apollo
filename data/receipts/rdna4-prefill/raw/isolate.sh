#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
TOM=/mnt/TG_2TB/Projects/Apollo/engines/tq_head/build_rocm/bin/llama-bench
BUUN=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-bench
: > $S/isolate.log
for pair in \
  "llama3b:/mnt/TG_2TB/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf" \
  "qwen9b:/mnt/TG_2TB/AI/Models/Qwen3.5-9B-UD-Q2_K_XL.gguf" ; do
  name="${pair%%:*}"; model="${pair#*:}"
  for fork in tom buun; do
    bin=$TOM; [ "$fork" = buun ] && bin=$BUUN
    out=$(LD_LIBRARY_PATH="$(dirname "$bin")" timeout 900 "$bin" -m "$model" \
          -ngl 99 -fa 1 -p 512 -n 128 -r 3 2>/dev/null | grep -E "pp512|tg128")
    echo "--- $name / $fork ---" >> $S/isolate.log
    echo "$out" >> $S/isolate.log
  done
done
echo "######## ISOLATE DONE" >> $S/isolate.log
