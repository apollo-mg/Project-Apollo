#!/usr/bin/env bash
# PREREG_STRATA_194_Q4XL (on .194, detached). Waits for Kolibri K5 to finish cleanly, deletes its Q3_K_S (registered
# housekeeping), then Strata setup for UD-Q4_K_XL on GPU 0 (download + sha256 + pack) and the arms in registered order.
cd "$(dirname "$0")"
L=$PWD/runs/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
R=$PWD/canonical_reasoning-v1.txt; C=$PWD/canonical_code-v1.txt; K5=$HOME/sbench/runs_k5/run.log
until grep -q K5_DONE $K5 2>/dev/null; do sleep 20; done
if [ "$(grep -c 'K5e c[0-9]* .*rc=0' $K5)" = 2 ] && grep -q 'K5a-d: rc=0' $K5; then
  rm -f -- $HOME/AI/Models/kolibri/Kolibri-1-Q3_K_S.gguf && log "Q4XL: K5 complete, Q3_K_S deleted"
else
  log "Q4XL: K5 did not finish cleanly; Q3_K_S kept, not starting"; log Q4XL_DONE; exit 1
fi
avail=$(df -BG --output=avail $HOME | tail -1 | tr -dc 0-9)
[ "$avail" -ge 118 ] || { log "Q4XL: only ${avail}G free, need 118"; log Q4XL_DONE; exit 1; }
log "Q4XL: setup starting, ${avail}G free"
(cd ~/strata && ./setup.sh --setup --family unsloth --model UD-Q4_K_XL --gpu 0 --cuda 12 --vision no --yes --no-start \
  --no-browser --data-dir $HOME/strata-data) > runs/strata-setup-q4xl.log 2>&1 < /dev/null
rc=$?; CFG=$(ls -t ~/strata/strata-*.json | grep -i 'q4_k_xl' | grep -v shared-settings | head -1)
log "Q4XL setup rc=$rc cfg=$CFG free=$(df -BG --output=avail $HOME | tail -1 | tr -d ' ')"
{ [ $rc = 0 ] && [ -n "$CFG" ]; } || { log Q4XL_DONE; exit 1; }
cp "$CFG" runs/strata_config_q4xl.json
export STRATA_CFG=$CFG
export LLAMA_MODEL=$(ls ~/strata-data/models/unsloth-UD-Q4_K_XL/*-00001-of-00004.gguf) HFID=unsloth/Qwen3.8-Flash-Next-GGUF QUANT=UD-Q4_K_XL
MTP="-md $HOME/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
F1="-fa on -fit on -fitt 4096 -lv 4"
F4="-sm layer -fa on -fit on -fitt 1024,1024,1024,4096 -lv 4"
SPEC="--spec-method mtp --spec-num-tokens 3"
./run194.sh strata Q_S1_r1 $R ""
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama Q_B1_r1 $R "$F1 $MTP" $SPEC
./run194.sh strata Q_S1_r2 $R ""
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama Q_B1_r2 $R "$F1 $MTP" $SPEC
./run194.sh strata Q_S1_c $C ""
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama Q_B1_c $C "$F1 $MTP" $SPEC
CUDA_VISIBLE_DEVICES=0 ./run194.sh llama Q_B1n_r $R "$F1"
./run194.sh llama Q_B4_r1 $R "$F4 $MTP" $SPEC
./run194.sh llama Q_B4_r2 $R "$F4 $MTP" $SPEC
L2=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("log",""))' "$CFG"); [ -f "$L2" ] && cp "$L2" runs/strata-engine-q4xl.log
log Q4XL_DONE
