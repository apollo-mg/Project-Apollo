#!/usr/bin/env bash
# Runtime answer to TheTom's #294 question: does the 20-60 VGPR residual left by #295
# cost anything real on RDNA4?
#
# Paired decode benchmark, pre-fix vs post-fix, same GPU / model / KV type / flags:
#   fca3093c9  pre-fix   (gfx1201: 98 FA kernels spilling, worst 735)
#   f6124e914  #295 merge (gfx1201: 41 spilling, worst 357)
#
# Two head dims on purpose:
#   D=128  Llama-3.2-3B-BF16  -> exercises <128,2,turbo-K,*>, the class he flags as
#                                "a shape decode really launches" and which does NOT
#                                reach zero on gfx1201 (survives at 23-57 VGPR).
#   D=256  Qwen3.5-9B-Q8_0    -> exercises residual buckets #1 (18 kernels @ 57) and
#                                #2 (4 kernels @ 357, the worst survivor).
#
# Pure decode (-p 0 -n 128): "decode regression" is a token-generation claim.
# GQA is 3:1 and 4:1, both below the 6:1 auto-asymmetric gate, so it cannot fire and
# silently swap K. Pinned to 0 regardless.
set -u
D128=/mnt/TG_2TB/AI/Models/Llama-3.2-3B-Instruct-BF16.gguf
D256=/mnt/TG_2TB/AI/Models/qwen35/plain-Q8_0.gguf
OUT=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
REPS=5

echo "### RDNA4 DECODE BENCH  $(date -Is)"
echo "### gpu: $(rocm-smi --showproductname --csv 2>/dev/null | tail -1)"
echo "### clocks/power cap: $(rocm-smi --showmaxpower --csv 2>/dev/null | tail -1)"
echo

for ref in fca3093c9 f6124e914; do
  B=/mnt/TG_2TB/AI/rdna4_$ref/build/bin/llama-bench
  [ -x "$B" ] || { echo "### $ref: NO BINARY, skipping"; continue; }
  echo "############ $ref ############"
  for pair in "D128:$D128" "D256:$D256"; do
    tag=${pair%%:*}; model=${pair#*:}
    [ -f "$model" ] || { echo "  $tag: model missing, skip"; continue; }
    for kv in f16 turbo2 turbo3 turbo4; do
      printf "%-10s %-6s %-8s " "$ref" "$tag" "$kv"
      TURBO_AUTO_ASYMMETRIC=0 "$B" -m "$model" -ngl 99 -fa 1 \
          -ctk "$kv" -ctv "$kv" -p 0 -n 128 -r $REPS -o csv 2>/dev/null \
        | awk -F',' 'NR>1 && $0 ~ /tg/ {gsub(/"/,"",$(NF-1)); gsub(/"/,"",$NF); print "tg128 = " $(NF-1) " +/- " $NF " t/s"; found=1}
                     END{ if(!found) print "FAILED / unsupported" }'
    done
  done
  echo
done
echo "### BENCH DONE $(date -Is)"
