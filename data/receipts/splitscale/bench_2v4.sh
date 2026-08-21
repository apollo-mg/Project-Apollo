#!/usr/bin/env bash
# 2-GPU vs 4-GPU tensor split, plus the concurrency arm. See PREREG_2V4.md.
set -u
B=~/llama_stock/build_puzzle/bin/llama-bench          # built 5m31s AFTER the sm_60 carve-out
M=~/AI/Models/Qwen3.8-27B/Qwen3.8-27B-Q6_K.gguf
COMMON="-m $M -ngl 99 -p 512 -n 128 -r 3 -o md"
export GGML_CUDA_ALLREDUCE=internal                   # NCCL is broken on these P100s

run () {  # run <label> <gpus> <numa|-> <split>
  local label=$1 gpus=$2 numa=$3 split=$4
  echo "### $label  gpus=$gpus numa=$numa sm=$split  $(date -Iseconds)"
  local pre=""
  [ "$numa" != "-" ] && pre="numactl --cpunodebind=$numa --membind=$numa"
  CUDA_VISIBLE_DEVICES=$gpus $pre $B $COMMON -sm "$split" 2>&1 | grep -vE "^$|^ggml_|^load_|^llama_"
  echo
}

echo "=== clock/power at start ==="
nvidia-smi --query-gpu=index,clocks.applications.graphics,power.limit,memory.used --format=csv,noheader
echo

run L2  0,1     0 layer
run T2a 0,1     0 tensor
run T2b 2,3     1 tensor
run T4  0,1,2,3 - tensor

echo "### CONC  T2a and T2b simultaneously  $(date -Iseconds)"
( CUDA_VISIBLE_DEVICES=0,1 numactl --cpunodebind=0 --membind=0 $B $COMMON -sm tensor 2>&1 \
    | grep -E "^\|" | sed 's/^/[A 0,1] /' ) &
PA=$!
( CUDA_VISIBLE_DEVICES=2,3 numactl --cpunodebind=1 --membind=1 $B $COMMON -sm tensor 2>&1 \
    | grep -E "^\|" | sed 's/^/[B 2,3] /' ) &
PB=$!
wait $PA $PB
echo
echo "=== clock/power at end (thermal/power drift check) ==="
nvidia-smi --query-gpu=index,clocks.sm,power.draw,temperature.gpu --format=csv,noheader
echo "### finished $(date -Iseconds)"
