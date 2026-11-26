#!/bin/bash
# PREREG_OLMO3_LADDER: OL_SFT, OL_DPO, OL_RL on the desktop (mainline 33aeb17f8 on ROCm 10.1 with Arch's HIP runtime).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/olmo3-ladder; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state_m1.log; log() { echo "$* $(date '+%F %T')" >> $S; }
BIN=$R/engines/rocm10/up_33aeb17f/build_rocm/bin; G=/mnt/HDD/Models/olmo3-7b-gguf; PORT=8095
FLAGS="-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0"
for spec in OL_SFT:Olmo-3-7B-Instruct-SFT OL_DPO:Olmo-3-7B-Instruct-DPO OL_RL:Olmo-3-7B-Instruct; do
  ARM=${spec%%:*}; M=$G/${spec#*:}-Q8_0.gguf; X=""
  [ $ARM = OL_RL ] && X="--chat-template-file $H/olmo3_instruct_sft_template.jinja"   # Deviation 1
  $R/tools/rocm101arch.sh $BIN/llama-server -m $M $FLAGS $X --host 127.0.0.1 --port $PORT > $H/raw/server_$ARM.log 2>&1 &
  SP=$!; ok=0; for i in $(seq 150); do curl -s 127.0.0.1:$PORT/health | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  if [ $ok = 1 ]; then
    ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm $ARM --max-tokens 1024 --usage --no-think-check --skip-slot \
        --meta "{\"model\": \"$(basename $M) ($(grep "^${spec#*:} rc=0" $H/raw/convert.log | awk '{print $3}' | cut -c1-16))\", \"commit\": \"33aeb17f8, ROCm 10.1 + Arch hip-runtime 10.1-2\", \"flags\": \"$FLAGS\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_OLMO3_LADDER.md\"}" > $H/raw/run_$ARM.log 2>&1 )
    log "$ARM rc=$? rows=$(( $(wc -l < $QA/raw/main_$ARM.jsonl) - 1 ))"
  else log "$ARM server failed"; fi
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
done
log LADDER_DONE
