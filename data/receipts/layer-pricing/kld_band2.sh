#!/usr/bin/env bash
# Large-transition bands, fp16->t4 then fp16->t2. Same cell design as kld_band.sh:
# one-step VBR_DEGRADE_ORDER demoting exactly one (layer,side), byte-identical otherwise.
#
# WHY: at fp16->t8 the per-cell price is real but the RANKING is not resolvable --
# rho_half 0.591 vs a 0.90 bar, median adjacent gap 0.18 cell-SE, ~615 h to close.
# The effect is simply too small. A larger transition raises effect/noise. Two questions:
#   1. does rho_half PASS at a big transition (is a price table obtainable at all)?
#   2. is the ranking TRANSITION-INVARIANT vs t8 (does one big scan buy the whole table)?
#   3. does layer 63 still invert (V costlier), or is that specific to t8?
# Not t1: 1.25 bpv risks KLD saturation, which would compress differences and destroy
# the very ranking being measured.
set -u
P=~/buun-llama-cpp/build_sm60_new/bin/llama-perplexity
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-UD-IQ4_XS.gguf
C=~/hazard_prompts_16k.txt
D=~/kldsweep; mkdir -p $D/orders
export GGML_CUDA_ALLREDUCE=internal
LAYERS="3 7 11 15 19 23 27 31 35 39 43 47 51 55 59 63"
for TIER in t4 t2; do
  echo "======== BAND fp16->$TIER  $(date -Iseconds)"
  for il in $LAYERS; do
    for side in k v; do
      tag="${il}${side}"
      out=$D/cell_${tag}_${TIER}.bin
      [ -f "$out" ] && { echo "skip $tag $TIER"; continue; }
      echo "${tag}:${TIER}" > $D/orders/${tag}_${TIER}.txt
      echo "### cell $tag  fp16->$TIER  $(date -Iseconds)"
      CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 env \
        TURBO_KLD_DUMP=$out VBR_DEGRADE_ORDER=$D/orders/${tag}_${TIER}.txt \
        $P -m $M -f $C -ngl 99 -c 4096 --chunks 8 -sm tensor -fit off \
        -ct vbr --vbr-floor $TIER --vbr-vram 64M \
        --kl-divergence --kl-divergence-base $D/base_f16.dat 2>&1 | \
        grep -iE "Same top p|Mean.*KLD|Median.*KLD|wrote" | head -4
    done
  done
done
echo "### bands done $(date -Iseconds)"
