#!/usr/bin/env bash
# LAYER-63 CONTROL. Qwen3.5-4B-Q5_K_S on .73 (2x P100 sm_60).
#
# THE QUESTION: on Qwen3.8-27B, cell 63v -- the V cache of the LAST full-attention KV
# layer -- is the single costliest cell in all three bands (t8/t4/t2), across a 1017x
# range of effect size. blk.64 there is the MTP head, so "terminal layer" and
# "MTP-adjacent" are perfectly confounded and only one of them generalises.
#
# Qwen3.5-4B breaks the confound: same qwen35 hybrid family, same every-4th KV layer
# spacing (3,7,...,31 -- verified from blk.N.attn_k tensor names), 8 KV layers, and
# NO MTP head (no nextn key in the metadata).
#
#   31v costliest  -> "protect the terminal layer V cache" is a real allocator rule
#   31v ordinary   -> the Qwen3.8 result is MTP-specific, and buun should not
#                     generalise it
set -u
B=~/buun_vbr/build/bin
M=/mnt/models/AI_Models/tqstudy/Qwen3.5-4B-Q5_K_S.gguf
C=~/hazard_prompts_16k.txt
D=~/kldsweep_4b; mkdir -p $D/orders
LAYERS="3 7 11 15 19 23 27 31"
COMMON="-ngl 99 -c 4096 --chunks 8 -sm layer -fit off"

if [ ! -f $D/base_f16.dat ]; then
  echo "### base f16 $(date -Iseconds)"
  $B/llama-perplexity -m $M -f $C $COMMON -ctk f16 -ctv f16 \
    --kl-divergence-base $D/base_f16.dat 2>&1 | tail -3
fi

echo "### anchor selfcheck (fp16 vs fp16 -- the null) $(date -Iseconds)"
[ -f $D/anchor_selfcheck.bin ] || TURBO_KLD_DUMP=$D/anchor_selfcheck.bin \
  $B/llama-perplexity -m $M -f $C $COMMON -ctk f16 -ctv f16 \
  --kl-divergence --kl-divergence-base $D/base_f16.dat 2>&1 | \
  grep -iE "Same top p|Mean.*KLD|wrote" | head -3

for TIER in t8 t4 t2; do
  echo "======== BAND fp16->$TIER  $(date -Iseconds)"
  for il in $LAYERS; do for side in k v; do
    tag="${il}${side}"; out=$D/cell_${tag}_${TIER}.bin
    [ -f "$out" ] && { echo "skip $tag $TIER"; continue; }
    echo "${tag}:${TIER}" > $D/orders/${tag}_${TIER}.txt
    echo "### cell $tag  fp16->$TIER  $(date -Iseconds)"
    TURBO_KLD_DUMP=$out VBR_DEGRADE_ORDER=$D/orders/${tag}_${TIER}.txt \
      $B/llama-perplexity -m $M -f $C $COMMON \
      -ct vbr --vbr-floor $TIER --vbr-vram 32M \
      --kl-divergence --kl-divergence-base $D/base_f16.dat 2>&1 | \
      grep -iE "Same top p|Mean.*KLD|wrote" | head -3
  done; done
done
echo "### 4B control done $(date -Iseconds)"
