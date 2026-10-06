#!/usr/bin/env bash
# PREREG_MOECACHE_194 arms on .194 (detached), via sbench/run194.sh with the PR build.
cd ~/sbench
export LLAMA_BIN=$HOME/k194/pr27861/build_sm60/bin/llama-server
export LLAMA_MODEL=$HOME/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf HFID=unsloth/Qwen3.8-Flash-Next-GGUF QUANT=UD-IQ4_XS
R=$PWD/canonical_reasoning-v1.txt; FIT="-sm layer -fa on -fit on -fitt 3072 -lv 4"
./run194.sh llama X0_r1 $R "$FIT"
./run194.sh llama X1_r1 $R "$FIT --moe-expert-cache 128"
./run194.sh llama X0_r2 $R "$FIT"
./run194.sh llama X1_r2 $R "$FIT --moe-expert-cache 128"
echo MOECACHE_DONE >> runs/run.log
