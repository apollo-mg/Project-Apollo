#!/usr/bin/env bash
# Drive the four pilot arms in sequence on .194 (one instrument, a server restart per arm). Resumable: run_pilot.py
# skips items already written, so re-running this script continues where it stopped.
set -uo pipefail
cd "$(dirname "$0")"
PY=../../../venv_cachyos/bin/python3
H=10.0.0.194
D='~/AI/Models'        # expanded on .194, not here
declare -A MODEL=(
  [C]=$D/ladder_ud/Qwen3.8-27B-Q8_0.gguf
  [M]=$D/ladder/Qwen3.8-27B-AD-IQ3_XXS.gguf
  [L]=$D/ladder/Qwen3.8-27B-AD-IQ2_XS.gguf
  [B]=$D/ladder/Ternary-Bonsai-2-27B-PQ2_0.gguf
)
for arm in ${ARMS:-C M L B}; do
  echo "=== arm $arm: ${MODEL[$arm]}"
  ssh -o BatchMode=yes $H "bash ~/qa_serve_arm.sh $arm ${MODEL[$arm]}" < /dev/null || { echo "arm $arm: server failed"; exit 1; }
  meta=$(ssh -o BatchMode=yes $H "cat ~/qa_meta_$arm.json" < /dev/null)
  mkdir -p raw/logs
  echo "$meta" > raw/logs/meta_$arm.json
  $PY run_pilot.py --url http://$H:8190 --arm $arm --meta "$meta" || { echo "arm $arm: runner failed"; exit 1; }
  scp -q $H:qa_pilot_server_$arm.log raw/logs/server_$arm.log && sed -i "s#/home/[a-z]*#~#g" raw/logs/server_$arm.log
done
ssh -o BatchMode=yes $H 'kill "$(cat ~/qa_pilot_server.pid)"' < /dev/null
echo "ALL ARMS DONE"
