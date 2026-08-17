#!/usr/bin/env bash
# Cross-fork KV codec ladder -- backlog N3: does TOM'S fork reproduce the two KV bugs
# that buun_vbr a8e5b5a38 showed on sm_60?
#
# Binary under test: ~/llama-cpp-turboquant/build/bin/llama-server
#   TheTom/llama-cpp-turboquant @ f6124e9 (the #295 merge commit), built sm_60 2026-08-17.
# Same model, same flags, same detector as ~/kv_pin2.sh so the two forks are comparable.
#
# buun_vbr reference outcomes (RESULT_TWO_KV_BUGS.md):
#   f16 + f16        clean
#   q8_0 + q8_0      COLLAPSE (22 responses, 0 exceptions)
#   q4_0 + q4_0      COLLAPSE 3/3
#   q8_0 + f16       HARD ABORT  ggml-backend-meta.cpp:533
#   f16 + q8_0       HARD ABORT
#   q8_0 + turbo4    clean 3/3
#
# TURBO_AUTO_ASYMMETRIC: Tom's fork silently upgrades K to q8_0 when the K type is a turbo
# type AND gqa_ratio >= 6 AND type_k == type_v (src/llama-kv-cache.cpp:147-161). This model
# is exactly 6:1, so EVERY arm pins it to 0 -- except T8, which deliberately leaves it on to
# document the upgrade. T7/T8 are otherwise byte-identical command lines.
set -u

B=~/llama-cpp-turboquant/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8092
OUT=~/xfork
mkdir -p $OUT

[ -x "$B" ] || { echo "FATAL: no binary at $B"; exit 1; }
[ -f "$M" ] || { echo "FATAL: no model at $M"; exit 1; }

echo "### CROSS-FORK KV LADDER"
echo "### binary : $B"
echo "### version: $($B --version 2>&1 | head -1)"
echo "### model  : $M"
echo "### start  : $(date -Is)"
echo "### clocks : $(nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader | tr '\n' ' | ')"
echo

# A real generation is the ONLY valid postcondition. /health has lied three separate ways:
# llama-swap answering on a neighbouring port, VRAM resident before the server accepts, and
# /health returning 503 while requests were already being served.
ready() {
  local name=$1
  for i in $(seq 1 100); do
    grep -q "GGML_ASSERT" $OUT/srv_$name.log 2>/dev/null && return 2
    pgrep -x llama-server >/dev/null || return 3
    r=$(curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null)
    echo "$r" | grep -q '"choices"' && return 0
    sleep 4
  done
  return 1
}

# Detector thresholds are the CORRECTED ones (AFM-15: maxrun>40 flagged a legitimate table
# rule as degeneration). Do not tighten without re-checking against a known-good response.
probe() {
  local name=$1
  for i in 1 2 3; do
    curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
      > $OUT/resp_${name}_$i.json 2>/dev/null
    python3 - "$OUT/resp_${name}_$i.json" "$i" <<'PY'
import json,sys
p,i = sys.argv[1], sys.argv[2]
try: d=json.load(open(p))
except Exception: print(f"  req{i} PARSE_FAIL"); raise SystemExit
if "choices" not in d: print(f"  req{i} ERR "+str(d)[:60]); raise SystemExit
m=d["choices"][0]["message"]; t=(m.get("content") or "")+(m.get("reasoning_content") or "")
if not t: print(f"  req{i} EMPTY"); raise SystemExit
run=mx=1; prev=""
for c in t:
    run = run+1 if c==prev else 1
    mx=max(mx,run); prev=c
bad = (mx>200 or len(set(t))<12)
tag = "DEGENERATE" if bad else "ok"
print(f"  req{i} {tag} len={len(t)} maxrun={mx} uniq={len(set(t))}")
if bad: print(f"       sample: {t[:110]!r}")
PY
  done
}

run() {
  local name=$1 asym=$2; shift 2
  echo "### $name : TURBO_AUTO_ASYMMETRIC=$asym : $*"
  pkill -x llama-server 2>/dev/null; sleep 5
  TURBO_AUTO_ASYMMETRIC=$asym setsid nohup $B -m $M -ngl 99 -c 16384 --jinja \
      --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$name.log 2>&1 < /dev/null &
  ready "$name"; rc=$?
  case $rc in
    0) probe "$name" ;;
    2) echo "  HARD ABORT"; grep -m2 -E "GGML_ASSERT|AllReduce" $OUT/srv_$name.log | sed 's/^/       /' ;;
    3) echo "  SERVER DIED (no assert)"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
    *) echo "  READY TIMEOUT"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
  esac
  # did the auto-asymmetric upgrade fire?
  if grep -q "auto-asymmetric" $OUT/srv_$name.log 2>/dev/null; then
    echo "  >> AUTO-ASYM FIRED: $(grep -m1 -o 'upgrading K from [a-z0-9_]* to q8_0' $OUT/srv_$name.log)"
  else
    echo "  >> auto-asym did not fire"
  fi
  echo
}

#   name  asym  flags
run T1 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk f16    -ctv f16      # control
run T2 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0   -ctv q8_0     # Bug A primary
run T3 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q4_0   -ctv q4_0     # Bug A 2nd stock codec
run T4 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0   -ctv f16      # Bug B
run T5 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk f16    -ctv q8_0     # Bug B
run T6 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0   -ctv turbo4   # speed+correctness config
run T7 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk turbo3 -ctv turbo3   # turbo sym, guard OFF
run T8 1 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk turbo3 -ctv turbo3   # turbo sym, guard ON
run T9 0 -sm layer               --spec-type draft-mtp -ctk q8_0   -ctv q8_0 # split-mode control

pkill -x llama-server 2>/dev/null
echo "### XFORK DONE $(date -Is)"
