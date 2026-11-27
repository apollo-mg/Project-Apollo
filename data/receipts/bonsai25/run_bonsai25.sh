#!/bin/bash
# PREREG_BONSAI25: Bonsai 2 PQ2_0 (same-day replay of BONB9) then Ternary-Bonsai-2.5-27B PQ2_0 on the desktop, both on
# PrismML 9a9394a89 build_hip (the BONB9 binary) via tools/rocm724.sh (pre-11-24 build). M1, thinking off, run_main
# defaults as BONB9 (max_tokens 1024, slot readout on, --expect-variants), plus --usage (records only).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/bonsai25; QA=$R/data/receipts/quant-abstention; PY=$R/venv_cachyos/bin/python3
S=$H/raw/state.log; log() { echo "$* $(date '+%F %T')" >> $S; }
BIN=$R/engines/prism_sep/build_hip/bin/llama-server; PORT=8097
FLAGS=(-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 -fit off -lv 4)
VAR='{" UNKNOWN": 59322, " Unknown": 21024, " unknown": 9496}'
for spec in "BON2R|/mnt/TG_2TB/AI/Models/bonsai2/Ternary-Bonsai-2-27B-PQ2_0.gguf" "BON25|/mnt/HDD/Models/bonsai-2.5-27b/Ternary-Bonsai-2.5-27B-PQ2_0.gguf"; do
  IFS='|' read -r ARM M <<< "$spec"
  $R/tools/rocm724.sh $BIN -m $M "${FLAGS[@]}" --host 127.0.0.1 --port $PORT > $H/raw/server_$ARM.log 2>&1 &
  SP=$!; ok=0; for i in $(seq 150); do curl -s 127.0.0.1:$PORT/health | grep -q ok && { ok=1; break; }; kill -0 $SP 2>/dev/null || break; sleep 2; done
  mp=$(curl -s -m 5 127.0.0.1:$PORT/props | $PY -c 'import json,sys; print(json.load(sys.stdin).get("model_path",""))')
  if [ $ok = 1 ] && [ "$mp" = "$M" ]; then
    curl -s -m 600 127.0.0.1:$PORT/v1/chat/completions -H 'content-type: application/json' \
      -d '{"messages":[{"role":"user","content":"Say ready."}],"max_tokens":8,"chat_template_kwargs":{"enable_thinking":false}}' > /dev/null
    META="{\"arm\": \"$ARM\", \"model\": \"$(basename $M) ($(sha256sum < $M | cut -c1-16))\", \"build\": \"prism 9a9394a89 build_hip, ROCm 7.2.4 runtime via tools/rocm724.sh\", \"host\": \"RX 9070 XT\", \"flags\": \"${FLAGS[*]}\", \"prereg\": \"PREREG_BONSAI25.md\"}"
    ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm $ARM --usage --meta "$META" --expect-variants "$VAR" > $H/raw/run_$ARM.log 2>&1 )
    log "$ARM rc=$? rows=$(( $(wc -l < $QA/raw/main_$ARM.jsonl) - 1 ))"
  else log "$ARM server failed (ok=$ok, model_path=$mp)"; fi
  kill $SP 2>/dev/null; wait $SP 2>/dev/null
done
log BONSAI_DONE
