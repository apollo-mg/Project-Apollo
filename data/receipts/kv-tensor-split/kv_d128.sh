#!/usr/bin/env bash
# N1: is the stock-quantized KV collapse specific to head_dim 256?
#
# Every result so far is on Qwen3.8-27B, D=256. The mechanism hypothesis is that the
# D=256 fused FA path is gated on turing_mma_available() || amd_wmma_available(), NEITHER
# true on sm_60, so it falls back to something that mishandles quantized K+V.
#
# That hypothesis predicts a D=128 model is CLEAN in the same configuration.
#
# Model: Llama-3.2-3B-Instruct-BF16, D=128, 24 heads / 8 KV (GQA 3:1), already on .73.
# The whole Qwen family here is D=256 (3.5-4B, 3.6-28B-REAP, 3.8-27B), so this is the
# only D=128 GGUF on the node. Note Qwen3.5-9B is ALSO D=256 -- BACKLOG N1 named it as
# the D=128 candidate and that was wrong.
#
# Two differences from the 27B ladders, both forced and both recorded:
#   - No MTP. Llama-3.2 has no draft head, so --spec-type is dropped. Harmless: the
#     collapse was already shown MTP-independent (RESULT_TWO_KV_BUGS P4).
#   - BF16 weights on sm_60. Pascal BF16 support is weak; L0 exists to catch that
#     before any conclusion is drawn from a later arm.
#
# GQA is 3:1, below Tom's 6:1 threshold, so TURBO_AUTO_ASYMMETRIC cannot fire here even
# if left at default. Pinned to 0 anyway.
set -u

B=~/llama-cpp-turboquant/build/bin/llama-server
M=~/AI/Models/tqstudy/Llama-3.2-3B-Instruct-BF16.gguf
PORT=8092
OUT=~/xfork_d128
mkdir -p $OUT

[ -x "$B" ] || { echo "FATAL: no binary"; exit 1; }
[ -f "$M" ] || { echo "FATAL: no model";  exit 1; }

echo "### D128 LADDER start $(date -Is)"
echo "### binary : $($B --version 2>&1 | head -1)"
echo "### model  : $M"
python3 ~/hd.py "$M" | sed 's/^/### geom  : /'
echo

port_free() {
  for i in $(seq 1 40); do
    pgrep -x llama-server >/dev/null && { sleep 2; continue; }
    (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { exec 3<&- 3>&-; sleep 2; continue; }
    return 0
  done
  echo "  WARN: port $PORT still held after 80s"; return 1
}

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
  local name=$1; shift
  echo "### $name : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup $B -m $M -ngl 99 -c 16384 --jinja \
      --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$name.log 2>&1 < /dev/null &
  ready "$name"; rc=$?
  case $rc in
    0) probe "$name" ;;
    2) echo "  HARD ABORT"; grep -m2 "GGML_ASSERT" $OUT/srv_$name.log | sed 's/^/       /' ;;
    3) echo "  SERVER DIED"; grep -m3 -E "E .*(requires|failed|error|support)" $OUT/srv_$name.log | sed 's/^/       /' ;;
    *) echo "  READY TIMEOUT"; tail -3 $OUT/srv_$name.log | sed 's/^/       /' ;;
  esac
  echo
}

# L0 GATE: does this BF16 model run at all on sm_60 under tensor split? If not, every
# arm below is uninterpretable and the ladder is abandoned rather than reported.
run L0 -sm tensor -ts 1,1 -ctk f16 -ctv f16

# THE TEST: D=256 collapses here. Does D=128?
run L1 -sm tensor -ts 1,1 -ctk q8_0   -ctv q8_0
run L2 -sm tensor -ts 1,1 -ctk q4_0   -ctv q4_0

# The abort classes at D=256, re-asked at D=128
run L3 -sm tensor -ts 1,1 -ctk q8_0   -ctv q4_0
run L4 -sm tensor -ts 1,1 -ctk turbo3 -ctv turbo3
run L5 -sm tensor -ts 1,1 -ctk iq4_nl -ctv iq4_nl

pkill -x llama-server 2>/dev/null
echo "### D128 LADDER DONE $(date -Is)"
