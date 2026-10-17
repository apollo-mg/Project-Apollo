#!/bin/bash
# PREREG_IDK_LORA Stage A, G41 rerun: Granite 4.1 has no thinking mode (its template never mentions think), so
# run_main needs --no-think-check, as PHI does. Waits for stageA.sh to finish, then runs IDK_B41 alone.
# launch, stopped by that PID after the arm). Logs in raw/.
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/idk-lora; G=/mnt/TG_2TB/models_small/gguf
SRV=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server; PY=$R/venv_cachyos/bin/python3; PORT=8095
mkdir -p $H/raw
until grep -q STAGEA_DONE $H/raw/stageA_state.log 2>/dev/null; do sleep 10; done
for spec in IDK_B41:granite-4.1-3b:--no-think-check; do
  ARM=${spec%%:*}; rest=${spec#*:}; M=${rest%%:*}; EXTRA=${rest#*:}
  F=$G/$M-Q8_0.gguf
  $SRV -m $F -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --host 127.0.0.1 --port $PORT > $H/raw/server_$ARM.log 2>&1 &
  SP=$!; echo $SP > $H/raw/server.pid
  for i in $(seq 120); do curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:$PORT/health 2>/dev/null | grep -q 200 && break; sleep 2; done
  echo "$ARM start $(date '+%F %T')" >> $H/raw/stageA_state.log
  META="{\"model\": \"$M-Q8_0.gguf\", \"bytes\": $(stat -c %s $F), \"build\": \"buun 38ada0e1b build_rocm\", \"host\": \"RX 9070 XT\", \"prereg\": \"PREREG_IDK_LORA.md\"}"
  ( cd $R/data/receipts/quant-abstention && $PY run_main.py --url http://127.0.0.1:$PORT --arm $ARM --max-tokens 1024 --usage \
      --meta "$META" $EXTRA > $H/raw/run_$ARM.log 2>&1 )
  echo "$ARM rc=$? rows=$(( $(cat $R/data/receipts/quant-abstention/raw/main_$ARM.jsonl 2>/dev/null | wc -l) - 1 )) $(date '+%F %T')" >> $H/raw/stageA_state.log
  kill $SP; wait $SP 2>/dev/null
done
echo STAGEA_B41_DONE >> $H/raw/stageA_state.log
