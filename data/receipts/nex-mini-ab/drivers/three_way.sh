#!/usr/bin/env bash
# nex-mini-ab three-way HumanEval+: R1 NEX|QWEN, R2 ORNITH|NEX -- concurrent 2-GPU pairs on .194.
# Runs ENTIRELY on .194 (setsid-detached) so a desktop reboot cannot kill it.
# Prereg (desktop repo): data/receipts/nex-mini-ab/PREREG_THREE_WAY.md
set -u
D=/home/mark/AI/Models/nex-mini-ab
BIN=/home/mark/buun-llama-cpp/build_sm60_head/bin/llama-server
HEP=/home/mark/hep
OUT=$HEP/out/nex3
PY=/home/mark/venv/bin/python3
mkdir -p "$OUT"
LOG=$OUT/driver.log
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }
declare -A FILE=([NEX]=nex-agi_Nex-N2.5-mini-Q4_K_M.gguf [QWEN]=Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf [ORNITH]=Ornith-1.5-35B-A3B-Q4_K_M.gguf)
declare -A TEMP=([NEX]=0.7 [QWEN]=0.6 [ORNITH]=0.6)
declare -A TOPK=([NEX]=40 [QWEN]=20 [ORNITH]=20)

clocks(){ echo "  clocks: $(nvidia-smi --query-gpu=index,clocks.applications.graphics,clocks.sm,power.limit,temperature.gpu --format=csv,noheader | tr '\n' ' ')" >> "$LOG"; }

start_srv(){   # start_srv ARM SLOT  -- slot A = GPUs 0,1 on NUMA node 0, slot B = GPUs 2,3 on node 1
  local arm=$1 slot=$2 gpus node port
  case $slot in A) gpus=0,1; node=0; port=8091;; B) gpus=2,3; node=1; port=8092;; esac
  CUDA_VISIBLE_DEVICES=$gpus setsid nohup numactl --cpunodebind=$node --preferred=$node \
    "$BIN" -m "$D/${FILE[$arm]}" -ngl 99 -sm layer -ts 1,1 -c 32768 -np 1 -fa on --jinja \
    --host 127.0.0.1 --port $port > "$OUT/server_${arm}_${ROUND}.log" 2>&1 < /dev/null &
}
ready(){       # a real 1-token completion, not /health (a 200 there is not a loaded model)
  local port=$1 i
  for i in $(seq 1 120); do
    curl -s -m 5 "http://127.0.0.1:$port/v1/chat/completions" -H 'Content-Type: application/json' \
      -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' 2>/dev/null \
      | grep -q finish_reason && return 0
    sleep 5
  done
  return 1
}
props(){
  curl -s -m 10 "http://127.0.0.1:$1/props" | "$PY" -c "import sys,json; d=json.load(sys.stdin); \
print('   loaded', d.get('model_path','?').split('/')[-1], '| n_ctx', (d.get('default_generation_settings') or {}).get('n_ctx'))" >> "$LOG" 2>&1
}
stop_all(){    # .194 is dedicated to this run; exact-name match, numeric PIDs, never pkill -f
  local p i
  for p in $(pgrep -x llama-server); do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 40); do pgrep -x llama-server >/dev/null || return 0; sleep 1; done
  say "  WARNING: llama-server still alive after 40 s"
}
hep(){         # hep ARM PORT -- one harness, every sampling value sent explicitly on every request
  local arm=$1 port=$2
  ( cd "$HEP" && HEP_MODEL="${arm}-${ROUND}" HEP_ENDPOINT="http://127.0.0.1:$port/v1/chat/completions" \
    HEP_TEMP=${TEMP[$arm]} HEP_TOP_P=0.95 HEP_TOP_K=${TOPK[$arm]} HEP_MIN_P=0 HEP_PRESENCE_PENALTY=0 \
    HEP_REPEAT_PENALTY=1.0 HEP_K=3 HEP_MAXTOK=16000 HEP_PREFIX=nex3 HEP_TAG="${arm}_${ROUND}" \
    timeout 12h "$PY" "$HEP/hep_eval.py" > "$OUT/hep_${arm}_${ROUND}.log" 2>&1 )
  local rc=$?
  say "  ${arm}_${ROUND} harness exit $rc | $(grep -m1 'pass@1 POOLED' "$OUT/hep_${arm}_${ROUND}.log")"
}
round(){       # round NAME ARM_ON_SLOT_A ARM_ON_SLOT_B
  ROUND=$1; local a=$2 b=$3
  say "=== ROUND $ROUND: $a on GPUs 0,1 (node 0, :8091) | $b on GPUs 2,3 (node 1, :8092) ==="
  stop_all; clocks
  start_srv "$a" A; start_srv "$b" B
  if ! ready 8091 || ! ready 8092; then say "  server(s) never ready -- round $ROUND aborted"; stop_all; return 1; fi
  say "  slot A ($a):"; props 8091
  say "  slot B ($b):"; props 8092
  hep "$a" 8091 &
  local pa=$!
  hep "$b" 8092 &
  local pb=$!
  wait "$pa"; wait "$pb"
  clocks; stop_all
  say "=== ROUND $ROUND done ==="
}

say "### three-way start on $(hostname): $("$BIN" --version 2>&1 | grep -m1 version) ###"
for arm in NEX QWEN ORNITH; do
  grep -q "VERIFIED ${FILE[$arm]}" "$D/download.log" || { say "NOT VERIFIED: ${FILE[$arm]} -- abort"; exit 1; }
done
round R1 NEX QWEN
round R2 ORNITH NEX
say "### THREE-WAY COMPLETE ###"
