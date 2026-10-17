#!/bin/bash
# Beam pelican server: PREREG_BEAM's placement (K spilled MoE layers, -ts TS, --no-op-offload) with -c 24576 for
# the pelican's 20000-token budget. serve_pelican.sh K TS
K=$1; TS=$2; O=$HOME/bench/beam-pelican-1017
L=$(tr " " "\n" < $HOME/bench/beam_moe_layers.txt | grep -v "^$" | tail -n $K | paste -sd"|")
OT="blk\.($L)\.ffn_[a-z_]*exps.*=CPU"
echo "K=$K ts=$TS start $(date +%T) $(nvidia-smi --query-gpu=index,power.limit,clocks.applications.graphics,memory.used --format=csv,noheader | tr "\n" ";")" >> $O/state.log
CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal exec $HOME/llama.cpp-beam/build_sm60/bin/llama-server \
  -m $HOME/AI/Models/beam_ad_iq2_xxs/Beam-1.0-501B-A23B-AD-IQ2_XXS-00001-of-00003.gguf \
  -ngl 99 -sm layer -c 24576 -ctk f16 -ctv f16 -np 1 -fit off -ts $TS -ot "$OT" --no-op-offload \
  --host 127.0.0.1 --port 8091 > $O/server_K$K.log 2>&1 < /dev/null
