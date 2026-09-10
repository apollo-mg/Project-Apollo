#!/usr/bin/env bash
# Controlled AD quant ladder. See PREREG_AD_QUANT_LADDER.md.
# One box, one binary, one backend, one packager. Bitrate is the only variable.
set -u
B=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp/build_rocm/bin/llama-server
PY=/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3
M=/mnt/TG_2TB/AI/Models
declare -A ARM=( [L1]=$M/Qwen3.8-27B-AD-IQ2_XS.gguf
                 [L2]=$M/Qwen3.8-27B-AD-IQ3_XXS.gguf
                 [L3]=$M/Qwen3.8-27B-AD-IQ3_S-IQ3_XXS.gguf )
for A in L1 L2 L3; do
  echo "######## arm=$A model=$(basename ${ARM[$A]})  $(date -Iseconds)"
  setsid nohup $B -m "${ARM[$A]}" -ngl 99 -c 8192 -fa on --host 127.0.0.1 --port 8085 \
      > /tmp/ladder_$A.log 2>&1 < /dev/null &
  pid=$!
  i=0; while [ $i -lt 90 ]; do grep -qa "listening on\|failed to load\|error while" /tmp/ladder_$A.log && break; i=$((i+1)); sleep 2; done
  if ! grep -qa "listening on" /tmp/ladder_$A.log; then
    echo "  -> $A did NOT start"; grep -aiE "failed|error" /tmp/ladder_$A.log | head -2
  else
    for REP in 1 2 3; do
      echo "---- $A rep=$REP $(date -Iseconds)"
      $PY -u run_fixture.py --host http://127.0.0.1:8085 --tier cal --effort medium \
          --sampling card --seed $((1000 + REP)) --jsonl "ladder_${A}_rep${REP}.jsonl" 2>&1 | tail -3
    done
  fi
  kill $pid 2>/dev/null; j=0
  while kill -0 $pid 2>/dev/null && [ $j -lt 30 ]; do j=$((j+1)); sleep 1; done
  kill -9 $pid 2>/dev/null
  while ss -ltn 2>/dev/null | grep -q ":8085 "; do sleep 1; done
  echo
done
echo "######## AD LADDER DONE $(date -Iseconds)"
