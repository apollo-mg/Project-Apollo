#!/usr/bin/env bash
# PREREG_STRATA_194_SPILL arms in registered order (on .194, detached).
cd "$(dirname "$0")"
export STRATA_CFG=$HOME/strata/strata-unsloth-ud-iq4_xs.json
R=$PWD/canonical_reasoning-v1.txt; C=$PWD/canonical_code-v1.txt
# S4 arms done in the first pass (Deviation 1 reruns only the buun arms)
rm -f "${STRATA_CFG%.json}.shared-settings.json" 2>/dev/null
export LLAMA_MODEL=$HOME/strata-data/models/unsloth-UD-IQ4_XS/Qwen3.8-Flash-Next-UD-IQ4_XS-00001-of-00003.gguf HFID=unsloth/Qwen3.8-Flash-Next-GGUF QUANT=UD-IQ4_XS
MTP="-md $HOME/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
N=""
for n in 4 6 8 10 12 14 16 20 24; do
  ./run194.sh llama L4_r1_ts_n$n $R "-sm layer -ts 1,1,1,0.6 -ngl 99 -fa on -fit off -lv 4 -ncmoe $n $MTP" --spec-method mtp --spec-num-tokens 3
  grep -q "L4_r1_ts_n$n: lmx rc=0" runs/run.log && { N=$n; break; }
done
[ -n "$N" ] || { echo "SPILL: no -ncmoe up to 24 served" >> runs/run.log; echo SPILL_DONE >> runs/run.log; exit 1; }
echo "SPILL: buun uses -ncmoe $N (static GPU share $(( (48 - N) * 100 / 48 ))%)" >> runs/run.log
./run194.sh llama L4_r2 $R "-sm layer -ts 1,1,1,0.6 -ngl 99 -fa on -fit off -lv 4 -ncmoe $N $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L4_c $C "-sm layer -ts 1,1,1,0.6 -ngl 99 -fa on -fit off -lv 4 -ncmoe $N $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L40_r $R "-sm layer -ts 1,1,1,0.6 -ngl 99 -fa on -fit off -lv 4 -ncmoe $N"
echo SPILL_DONE >> runs/run.log
