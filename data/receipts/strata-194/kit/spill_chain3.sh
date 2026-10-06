#!/usr/bin/env bash
# Deviation 2: buun arms with llama.cpp auto-fit (per-device margins) instead of -ncmoe.
cd "$(dirname "$0")"
R=$PWD/canonical_reasoning-v1.txt; C=$PWD/canonical_code-v1.txt
export LLAMA_MODEL=$HOME/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf HFID=unsloth/Qwen3.8-Flash-Next-GGUF QUANT=UD-IQ4_XS
MTP="-md $HOME/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
FIT="-sm layer -fa on -fit on -fitt 1024,1024,1024,4096 -lv 4"
./run194.sh llama L4_r1 $R "$FIT $MTP" --spec-method mtp --spec-num-tokens 3
grep -q "L4_r1: lmx rc=0" runs/run.log || { echo "SPILL3: auto-fit + MTP failed" >> runs/run.log; echo SPILL3_DONE >> runs/run.log; exit 1; }
./run194.sh llama L4_r2 $R "$FIT $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L4_c $C "$FIT $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L40_r $R "$FIT"
echo SPILL3_DONE >> runs/run.log
