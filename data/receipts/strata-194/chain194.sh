#!/usr/bin/env bash
# PREREG_STRATA_194 arms in registered order (runs ON .194, detached).
cd "$(dirname "$0")"
export STRATA_CFG=$HOME/strata/strata-iq3_xxs.json
R=$PWD/canonical_reasoning-v1.txt; C=$PWD/canonical_code-v1.txt
MTP="-md $HOME/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
./run194.sh strata S_r1 $R ""
./run194.sh strata S_r2 $R ""
./run194.sh strata S_c $C ""
rm -f "${STRATA_CFG%.json}.shared-settings.json"
SPLIT="-sm tensor -ts 1,1,1,0.75"
./run194.sh llama L_r1 $R "-ngl 99 -fa on -fit off -lv 4 $SPLIT $MTP" --spec-method mtp --spec-num-tokens 3
if ! grep -q "L_r1: lmx rc=0" runs/run.log; then
  SPLIT="-sm layer"; echo "fallback: layer split for the llama arms (prereg)" >> runs/run.log
  ./run194.sh llama L_r1_layer $R "-ngl 99 -fa on -fit off -lv 4 $SPLIT $MTP" --spec-method mtp --spec-num-tokens 3
fi
./run194.sh llama L_r2 $R "-ngl 99 -fa on -fit off -lv 4 $SPLIT $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L_c $C "-ngl 99 -fa on -fit off -lv 4 $SPLIT $MTP" --spec-method mtp --spec-num-tokens 3
./run194.sh llama L0_r $R "-ngl 99 -fa on -fit off -lv 4 $SPLIT"
echo CHAIN_DONE >> runs/run.log
