#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
M=/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
run() { # name binary
  local n="$1" b="$2"
  echo "=== $n ===" | tee -a $S/forkbench.log
  rocm-smi --showclocks --showpower 2>/dev/null | grep -oE "sclk.*|Average Graphics Package Power \(W\): [0-9.]+" | head -2 | sed 's/^/  /' | tee -a $S/forkbench.log
  LD_LIBRARY_PATH="$(dirname "$b")" timeout 2400 "$b" -m "$M" -ngl 99 -fa 1 -p 512 -n 128 -r 5 -o json > $S/fb_$n.json 2> $S/fb_$n.err
  echo "  exit=$? $(grep -ciE 'error|fail' $S/fb_$n.err) err-lines" | tee -a $S/forkbench.log
}
: > $S/forkbench.log
run tom  /mnt/TG_2TB/Projects/Apollo/engines/tq_head/build_rocm/bin/llama-bench
run buun /mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-bench
echo "######## FORKBENCH DONE" | tee -a $S/forkbench.log
