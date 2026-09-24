#!/bin/bash
# Runs ON .194. PREREG_HESITATION_KLD.md.  ./run_hes.sh ARM [ARM...]   (REF first)
# Resumable: an arm whose dump exists is skipped. Completion is judged by the log line, not rc
# (llama-perplexity exits 0 on failure; KLD mode prints 'Mean    KLD:', PPL mode 'Final estimate').
set -u
W=~/hes
P=~/buun-llama-cpp/build_sm60_0920/bin/llama-perplexity   # buun 08826ad6e
M=~/AI/Models/ladder_ud
C=$W/corpus_reasoning.txt
BASE=$W/base_q8_u16.kld
export GGML_CUDA_ALLREDUCE=internal CUDA_VISIBLE_DEVICES=0,1,2,3
FLAGS=(-ngl 99 -sm layer -fa on -ctk f16 -ctv f16 -c 2048 -b 512 -ub 512)
mkdir -p $W/dumps $W/logs
model_of () { case $1 in
  REF)   echo $M/Qwen3.8-27B-Q8_0.gguf;;
  Q2KXL) echo $M/Qwen3.8-27B-UD-Q2_K_XL.gguf;;
  IQ3XXS) echo $M/Qwen3.8-27B-UD-IQ3_XXS.gguf;;
  IQ4XS) echo $M/Qwen3.8-27B-UD-IQ4_XS.gguf;;
  Q4KM)  echo $M/Qwen3.8-27B-UD-Q4_K_M.gguf;;
  Q6K)   echo ~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf;;
  *) echo "";; esac; }
for A in "$@"; do
  MOD=$(model_of $A); [ -f "$MOD" ] || { echo "ABORT: no model for $A"; exit 2; }
  L=$W/logs/$A.log; t0=$(date +%s)
  echo "######## $A $(date -Is) $(nvidia-smi --query-gpu=clocks.sm,power.limit --format=csv,noheader | head -1)"
  if [ $A = REF ]; then
    [ -s $BASE ] && { echo "skip REF"; continue; }
    $P -m $MOD -f $C "${FLAGS[@]}" --kl-divergence-base $BASE > $L 2>&1
    grep -q "Final estimate" $L || { echo "ABORT: REF failed"; rm -f $BASE; tail -5 $L; exit 1; }
    echo "   REF ok $(( $(date +%s)-t0 ))s base $(stat -c %s $BASE) B"
  else
    D=$W/dumps/$A.kld.bin; [ -s $D ] && { echo "skip $A"; continue; }
    TURBO_KLD_DUMP=$D.part $P -m $MOD -f $C "${FLAGS[@]}" --kl-divergence --kl-divergence-base $BASE > $L 2>&1
    if grep -q "Mean    KLD:" $L && [ -s $D.part ]; then mv $D.part $D; else echo "ABORT: $A failed"; tail -5 $L; exit 1; fi
    echo "   $A ok $(( $(date +%s)-t0 ))s $(grep -m1 'Mean    KLD:' $L)"
  fi
done
echo "######## HES DONE $(date -Is)"
