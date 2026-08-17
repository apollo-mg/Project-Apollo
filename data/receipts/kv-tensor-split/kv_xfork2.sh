#!/usr/bin/env bash
# Follow-up to kv_xfork.sh. The first ladder established, on BOTH forks, that stock
# quantized KV collapses only when K AND V are both quantized -- either side alone is clean:
#
#   q8_0 + q8_0   COLLAPSE 3/3     (512 consecutive '/' , finish_reason=length)
#   q8_0 + f16    clean 3/3
#   f16  + q8_0   clean 3/3
#   f16  + f16    clean 3/3
#
# That isolation was impossible on buun's fork because both mixed pairs abort there.
#
# This ladder asks the three questions that follow, cheapest-decisive-first.
set -u

TOM=~/llama-cpp-turboquant/build/bin/llama-server
BUUN=~/buun_vbr/build/bin/llama-server
M=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8092
OUT=~/xfork2
mkdir -p $OUT

[ -x "$TOM" ]  || { echo "FATAL: no Tom binary";  exit 1; }
[ -x "$BUUN" ] || { echo "FATAL: no buun binary"; exit 1; }
[ -f "$M" ]    || { echo "FATAL: no model";       exit 1; }

echo "### XFORK2 start $(date -Is)"
echo "### tom : $($TOM --version 2>&1 | head -1)"
echo "### buun: $($BUUN --version 2>&1 | head -1)"
echo

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

probe() {
  local name=$1
  for i in 1 2 3; do
    curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
      > $OUT/resp_${name}_$i.json 2>/dev/null
    python3 - "$OUT/resp_${name}_$i.json" "$i" <<'PY'
import json,sys,collections
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
top = collections.Counter(t).most_common(2)
print(f"  req{i} {'DEGENERATE' if bad else 'ok'} len={len(t)} maxrun={mx} uniq={len(set(t))}"
      + (f"  top={top}" if bad else ""))
PY
  done
}

run() {
  local name=$1 bin=$2 asym=$3; shift 3
  echo "### $name [$(basename $(dirname $(dirname $bin)))] asym=$asym : $*"
  pkill -x llama-server 2>/dev/null; sleep 5
  TURBO_AUTO_ASYMMETRIC=$asym setsid nohup $bin -m $M -ngl 99 -c 16384 --jinja \
      --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$name.log 2>&1 < /dev/null &
  ready "$name"; rc=$?
  case $rc in
    0) probe "$name" ;;
    2) echo "  HARD ABORT"; grep -m2 -E "GGML_ASSERT" $OUT/srv_$name.log | sed 's/^/       /' ;;
    3) echo "  SERVER DIED"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
    *) echo "  READY TIMEOUT"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
  esac
  grep -q "auto-asymmetric" $OUT/srv_$name.log 2>/dev/null && echo "  >> AUTO-ASYM FIRED"
  echo
}

# --- Q1: is it the FLASH-ATTENTION path? The single most decisive arm. -------------
# The D=256 dispatch table lives in fattn.cu and the fused path is gated on
# turing_mma_available() || amd_wmma_available(), NEITHER true on sm_60. If -fa off is
# clean while -fa on collapses, the bug is localised to FA kernel dispatch on Pascal --
# a specific, reportable defect rather than "quantized KV is broken".
run U1 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -fa off -ctk q8_0 -ctv q8_0
run U2 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -fa on  -ctk q8_0 -ctv q8_0   # paired control
run U3 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -fa off -ctk q4_0 -ctv q4_0

# --- Q2: "both stock" or "both the SAME stock type"? -------------------------------
run U4 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0 -ctv q4_0
run U5 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q4_0 -ctv q8_0

# --- Q3: breadth across the stock grid --------------------------------------------
run U6 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q5_1   -ctv q5_1
run U7 $TOM 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk iq4_nl -ctv iq4_nl

# --- Q3b: does the turbo3-symmetric ABORT need tensor split? ----------------------
# T7 (turbo3+turbo3, guard off, -sm tensor) hit the SAME assert buun's fork throws for
# mixed f16/quantized pairs: ggml-backend-meta.cpp:535 SPLIT_AXIS_UNKNOWN. That file is
# shared between the forks, so the defect is shared and only the trigger set differs.
# If -sm layer is clean, the abort is specifically the split-axis path, which is what the
# file name implies but nothing has yet tested.
run U9  $TOM 0 -sm layer --spec-type draft-mtp -ctk turbo3 -ctv turbo3
# NOT re-run here: -sm layer + q8_0 K+V. kv_xfork.sh T9 already collapsed 3/3 under layer
# split, matching buun. The collapse is split-independent on both forks; only the ABORT
# still needs its split-mode control, which is U9.

# --- Q4: does buun's fork emit the SAME character? --------------------------------
# The buun run recorded len=512 maxrun=512 uniq=1 but never saved a body, so the
# '/' is confirmed on Tom's fork only. Same statistics != same failure.
run U8 $BUUN 0 -sm tensor -ts 1,1 --spec-type draft-mtp -ctk q8_0 -ctv q8_0

pkill -x llama-server 2>/dev/null
echo "### XFORK2 DONE $(date -Is)"
