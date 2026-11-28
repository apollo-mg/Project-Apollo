#!/bin/bash
# PREREG_INKLING_STRATA: INKS20 (SQ-20 pack, lossless repack of the NVFP4 release), INKS20V2 (Strata's default SQv2-20), INKS10 (SQ-10) on Strata 0.2.23
# (Inkling engine 0.1.70, CUDA 12) on .73's two P100s; M1 driven from the desktop through the tunnel, as INK: reasoning_effort
# "none", greedy, 4,096 tokens, slot readout skipped; plus neutral penalties (Strata otherwise adds the card's).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/inkling-strata; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
. $H/strata73.sh
take_73
for spec in "INKS20:~/inkling-sq20v1/Inkling-2-Mini-SQ-20.strata" INKS20V2:SQ-20 INKS10:SQ-10; do
  ARM=${spec%%:*}; PACK=${spec#*:}
  if serve_pack $ARM $PACK; then
    log "$ARM served: $(curl -s 127.0.0.1:$TPORT/v1/models | head -c 300)"
    ( cd $QA && $PY run_main.py --url http://127.0.0.1:$TPORT --arm $ARM --max-tokens 4096 --timeout 900 --usage --skip-slot --no-think-check --chat-only \
        --neutral-penalties --template-kwargs '{"reasoning_effort": "none"}' \
        --meta "{\"model\": \"Inkling-2-Mini $PACK (Strata pack)\", \"engine\": \"Strata 0.2.23, inkling engine 0.1.70 cuda12\", \"flags\": \"$LAUNCH\", \"host\": \".73 2x P100\", \"prereg\": \"PREREG_INKLING_STRATA.md\"}" > $H/raw/run_$ARM.log 2>&1 )
    log "$ARM rc=$? rows=$(( $(wc -l < $QA/raw/main_$ARM.jsonl) - 1 ))"
  else log "$ARM did not serve"; fi
  stop_pack; rx "cat ~/strata_launch_$ARM.log" > $H/raw/strata_launch_$ARM.log 2>&1; sed -i 's#/home/mark/#~/#g' $H/raw/strata_launch_$ARM.log
done
give_73; log STRATA_INK_DONE
