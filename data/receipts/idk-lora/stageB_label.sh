#!/bin/bash
# PREREG_IDK_LORA: label the training pool with G41 (waits for the Stage A G41 rerun), fresh server, PID recorded.
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/idk-lora; G=/mnt/TG_2TB/models_small/gguf
SRV=$R/engines/buun-llama-cpp/build_rocm/bin/llama-server; PY=$R/venv_cachyos/bin/python3; PORT=8095
until grep -q STAGEA_B41_DONE $H/raw/stageA_state.log 2>/dev/null; do sleep 10; done
$SRV -m $G/granite-4.1-3b-Q8_0.gguf -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --host 127.0.0.1 --port $PORT > $H/raw/server_label.log 2>&1 &
SP=$!; echo $SP > $H/raw/server.pid
for i in $(seq 120); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && break; sleep 2; done
echo "label start $(date '+%F %T')" >> $H/raw/stageA_state.log
$PY $H/label_pool.py http://127.0.0.1:$PORT > $H/raw/label.log 2>&1
echo "label rc=$? rows=$(wc -l < $H/raw/labels_G41.jsonl) $(date '+%F %T')" >> $H/raw/stageA_state.log
kill $SP; wait $SP 2>/dev/null
echo LABEL_DONE >> $H/raw/stageA_state.log
