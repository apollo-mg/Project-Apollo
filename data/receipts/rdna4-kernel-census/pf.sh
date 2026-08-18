#!/usr/bin/env bash
B=/mnt/TG_2TB/AI/rdna4_f6124e914/build/bin/llama-bench
M=/mnt/TG_2TB/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf
for pair in "turbo3:q8_0" "turbo3:turbo3" "q8_0:q8_0" "f16:f16" "turbo4:q8_0" "turbo2:q8_0"; do
  k=${pair%%:*}; v=${pair#*:}
  out=$(TURBO_AUTO_ASYMMETRIC=0 timeout 200 "$B" -m "$M" -ngl 99 -fa 1 -ctk "$k" -ctv "$v" -p 256 -n 0 -r 1 2>&1)
  if echo "$out" | grep -q "ROCm error"; then
    res="ABORT  $(echo "$out" | grep -m1 -oE 'ggml-cuda.cu:[0-9]+: ROCm error')"
  else
    res="ok  $(echo "$out" | grep -oE '[0-9]+\.[0-9]+ ± [0-9]+\.[0-9]+' | head -1) t/s"
  fi
  printf '  %-16s %s\n' "$k/$v" "$res"
done
