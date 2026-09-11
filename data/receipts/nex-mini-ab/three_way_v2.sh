#!/usr/bin/env bash
# nex-mini-ab three-way, v2 (PREREG_THREE_WAY.md, Amendments 1 and 2):
#   slot A (GPUs 0,1): NEX_R1  -> ORNITH_R2 as soon as NEX_R1 finishes
#   slot B (GPUs 2,3): QWEN_R1 -> NEX_R2    as soon as QWEN_R1 finishes
# v2 exists because v1 omitted -ctk/-ctv and buun's fork then arms VBR dynamic KV by default.
# f16 KV is now explicit, and a guard aborts any arm whose server still arms VBR.
# Servers are stopped BY PORT (verified numeric PIDs), never all at once.
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
pid_on_port(){ local port=$1 p; for p in $(pgrep -x llama-server); do tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | grep -q -- "--port $port " && echo "$p"; done; }
stop_port(){
  local port=$1 p i
  for p in $(pid_on_port "$port"); do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 40); do [ -z "$(pid_on_port "$port")" ] && return 0; sleep 1; done
  say "  WARNING: server on :$port still alive after 40 s"
}
start_srv(){   # start_srv ARM SLOT ROUND
  local arm=$1 slot=$2 round=$3 gpus node port
  case $slot in A) gpus=0,1; node=0; port=8091;; B) gpus=2,3; node=1; port=8092;; esac
  CUDA_VISIBLE_DEVICES=$gpus setsid nohup numactl --cpunodebind=$node --preferred=$node \
    "$BIN" -m "$D/${FILE[$arm]}" -ngl 99 -sm layer -ts 1,1 -c 32768 -np 1 -fa on --jinja \
    -ctk f16 -ctv f16 \
    --host 127.0.0.1 --port $port > "$OUT/server_${arm}_${round}.log" 2>&1 < /dev/null &
}
ready(){
  local port=$1 i
  for i in $(seq 1 120); do
    curl -s -m 5 "http://127.0.0.1:$port/v1/chat/completions" -H 'Content-Type: application/json' \
      -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' 2>/dev/null \
      | grep -q finish_reason && return 0
    sleep 5
  done
  return 1
}
guard(){       # guard ARM ROUND PORT -- the KV type must really be f16; abort the arm otherwise
  local log="$OUT/server_$1_$2.log"
  if grep -q "VBR dynamic" "$log"; then
    say "  ABORT $1_$2: server armed VBR despite -ctk/-ctv f16"; stop_port "$3"; return 1
  fi
  grep -i -E "kv|cache" "$log" | grep -i -E "MiB|type|f16" | head -4 | sed 's/^/    kv: /' >> "$LOG"
  return 0
}
props(){
  curl -s -m 10 "http://127.0.0.1:$1/props" | "$PY" -c "import sys,json; d=json.load(sys.stdin); \
print('   loaded', d.get('model_path','?').split('/')[-1], '| n_ctx', (d.get('default_generation_settings') or {}).get('n_ctx'))" >> "$LOG" 2>&1
}
hep(){         # hep ARM PORT ROUND
  local arm=$1 port=$2 round=$3 tag="$1_$3"
  ( cd "$HEP" && HEP_MODEL="$tag" HEP_ENDPOINT="http://127.0.0.1:$port/v1/chat/completions" \
    HEP_TEMP=${TEMP[$arm]} HEP_TOP_P=0.95 HEP_TOP_K=${TOPK[$arm]} HEP_MIN_P=0 HEP_PRESENCE_PENALTY=0 \
    HEP_REPEAT_PENALTY=1.0 HEP_K=3 HEP_MAXTOK=16000 HEP_PREFIX=nex3 HEP_TAG="$tag" \
    timeout 12h "$PY" "$HEP/hep_eval.py" > "$OUT/hep_${tag}.log" 2>&1 )
  local rc=$?
  say "  $tag harness exit $rc | $(grep -m1 'pass@1 POOLED' "$OUT/hep_${tag}.log")"
}
arm_run(){     # arm_run ARM SLOT ROUND -- start server, check it, run the harness, stop the server
  local arm=$1 slot=$2 round=$3 port
  case $slot in A) port=8091;; B) port=8092;; esac
  stop_port "$port"; clocks
  start_srv "$arm" "$slot" "$round"
  if ! ready "$port"; then say "  ${arm}_${round} server never ready on :$port -- aborted"; stop_port "$port"; return 1; fi
  guard "$arm" "$round" "$port" || return 1
  say "  slot $slot (${arm}_${round}):"; props "$port"
  hep "$arm" "$port" "$round"
  stop_port "$port"; clocks
}

say "### three-way v2 on $(hostname): $("$BIN" --version 2>&1 | grep -m1 version) | f16 KV explicit ###"
for arm in NEX QWEN ORNITH; do
  grep -q "VERIFIED ${FILE[$arm]}" "$D/download.log" || { say "NOT VERIFIED: ${FILE[$arm]} -- abort"; exit 1; }
done
( arm_run NEX A R1 && arm_run ORNITH A R2; say "  slot A chain done" ) &
ca=$!
( arm_run QWEN B R1 && arm_run NEX B R2; say "  slot B chain done" ) &
cb=$!
wait "$ca"; wait "$cb"
say "### THREE-WAY COMPLETE (v2) ###"
