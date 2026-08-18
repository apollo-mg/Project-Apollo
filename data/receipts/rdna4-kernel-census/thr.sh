#!/usr/bin/env bash
B=/mnt/TG_2TB/AI/rdna4_f6124e914/build/bin/llama-bench
M=/mnt/TG_2TB/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf
echo "prompt-length threshold for the quantized-KV prefill abort (turbo3 K / q8_0 V, ub=512):"
for p in 4 8 9 16 32 64 128; do
  out=$(TURBO_AUTO_ASYMMETRIC=0 timeout 200 "$B" -m "$M" -ngl 99 -fa 1 -ctk turbo3 -ctv q8_0 -p $p -n 0 -r 1 2>&1)
  if echo "$out" | grep -q "ROCm error"; then r="ABORT"; else r="ok"; fi
  printf '  -p %-5s %s\n' "$p" "$r"
done
echo
echo "same, but forcing small ubatch (-ub 8) at -p 256:"
out=$(TURBO_AUTO_ASYMMETRIC=0 timeout 200 "$B" -m "$M" -ngl 99 -fa 1 -ctk turbo3 -ctv q8_0 -p 256 -n 0 -ub 8 -b 8 -r 1 2>&1)
echo "$out" | grep -q "ROCm error" && echo "  -p 256 -ub 8 -b 8 : ABORT" || echo "  -p 256 -ub 8 -b 8 : ok  $(echo "$out" | grep -oE '[0-9]+\.[0-9]+ ± [0-9]+\.[0-9]+' | head -1)"
