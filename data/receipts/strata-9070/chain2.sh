#!/usr/bin/env bash
# PREREG_STRATA_9070 remaining arms: S_code x2, S_nomtp, then L_code (llama.cpp, -ncmoe stepped up from 26 until it fits).
cd "$(dirname "$0")"
CFG=/mnt/TG_2TB/Projects/strata/strata-coder-iq1_m.json; P=../gemma4-9070-spec
./run_strata.sh S_code_r1 $CFG $P/canonical_code-v1.txt
./run_strata.sh S_code_r2 $CFG $P/canonical_code-v1.txt
./run_strata.sh S_nomtp ${CFG%.json}-nomtp.json $P/canonical_code-v1.txt
export LMX=~/.local/bin/lmx PFILE=$PWD/$P/canonical_code-v1.txt PROXY=1 CTX=8192 \
  MODEL=/mnt/TG_2TB/AI/strata-data/models/coder-IQ1_M/Qwen3.8-Flash-Next-GSQ-RCO-IQ1_M-00001-of-00002.gguf \
  HFID=ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF QUANT=IQ1_M
for n in 26 28 30 32 34 36 40; do
  ./run_llama.sh L_code_ncmoe$n "--reasoning off -ncmoe $n" 2>&1 | tail -3
  grep -q "L_code_ncmoe$n: lmx rc=0" runs/run.log && { echo "L_code used -ncmoe $n" >> runs/run.log; break; }
done
echo CHAIN2_DONE >> runs/run.log
