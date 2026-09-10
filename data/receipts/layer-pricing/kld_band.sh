#!/usr/bin/env bash
# fp16->t8 band, Qwen3.8-27B: 16 KV layers x 2 sides = 32 cells.
# Each cell = a ONE-STEP VBR_DEGRADE_ORDER demoting exactly that (layer,side) to t8,
# byte-identical to the anchor otherwise. That is the "one unit moved one tier" cell design
# from METHODOLOGY.md; there is no force-unit env var (I checked).
# Gates passed: fp16 anchor Same-top-p 100.000 +/- 0.000%.
set -u
P=~/buun-llama-cpp/build_sm60_new/bin/llama-perplexity
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-UD-IQ4_XS.gguf
C=~/hazard_prompts_16k.txt
D=~/kldsweep; mkdir -p $D/orders
export GGML_CUDA_ALLREDUCE=internal
LAYERS="3 7 11 15 19 23 27 31 35 39 43 47 51 55 59 63"
for il in $LAYERS; do
  for side in k v; do
    tag="${il}${side}"
    out=$D/cell_${tag}_t8.bin
    [ -f "$out" ] && { echo "skip $tag"; continue; }
    echo "${tag}:t8" > $D/orders/$tag.txt
    echo "### cell $tag  fp16->t8  $(date -Iseconds)"
    CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 env \
      TURBO_KLD_DUMP=$out VBR_DEGRADE_ORDER=$D/orders/$tag.txt \
      $P -m $M -f $C -ngl 99 -c 4096 --chunks 8 -sm tensor -fit off \
      -ct vbr --vbr-floor t8 --vbr-vram 64M \
      --kl-divergence --kl-divergence-base $D/base_f16.dat 2>&1 | \
      grep -iE "Same top p|Mean.*KLD|Median.*KLD|wrote" | head -4
  done
done
echo "### band done $(date -Iseconds)"
