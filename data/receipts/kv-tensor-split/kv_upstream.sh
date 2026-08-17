#!/usr/bin/env bash
# C3 TEST: does GENUINE upstream llama.cpp collapse on sm_60 with q8_0 K+V at D=256?
#
#   COLLAPSE -> upstream bug; both forks inherited it. Report goes upstream.
#   CLEAN    -> introduced in the shared fork ancestry. Two-maintainer report.
#
# Model: Qwen3.5-4B-BF16 (D=256, GQA 4:1, BF16, no MTP) -- the matched-pair model that
# collapses 3/3 on TheTom f6124e9. Small, so a failed arch load is cheap to discover.
#
# NOTE: no -sm tensor. That is a fork flag, and upstream has none/layer/row. The collapse
# is split-independent on both forks (kv_xfork T9, kv_fa F2), so layer split is valid here.
set -u
B=~/llama_upstream/build/bin/llama-server
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
M2=~/models/unsloth-Qwen3.8-27B-Q6_K.gguf
PORT=8093; OUT=~/xfork_upstream; mkdir -p $OUT
[ -x "$B" ] || { echo "FATAL: no upstream binary"; exit 1; }
echo "### UPSTREAM KV TEST $(date -Is)"
echo "### binary : $($B --version 2>&1 | head -1)"
echo "### HEAD   : $(git -C ~/llama_upstream log -1 --format='%h %s')"
echo
port_free(){ for i in $(seq 1 40); do pgrep -x llama-server >/dev/null && { sleep 2; continue; }
  (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { exec 3<&- 3>&-; sleep 2; continue; }; return 0; done; return 1; }
probe(){ local n=$1; for i in 1 2 3; do
  curl -s --max-time 400 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
    -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Explain how a $i-stage CPU pipeline works, with examples.\"}],\"temperature\":1.0,\"top_p\":0.95,\"top_k\":20,\"n_predict\":512,\"cache_prompt\":false}" \
    > $OUT/resp_${n}_$i.json 2>/dev/null
  python3 - "$OUT/resp_${n}_$i.json" "$i" <<'PY'
import json,sys,collections
p,i=sys.argv[1],sys.argv[2]
try: d=json.load(open(p))
except Exception: print(f"  req{i} PARSE_FAIL"); raise SystemExit
if "choices" not in d: print(f"  req{i} ERR "+str(d)[:60]); raise SystemExit
m=d["choices"][0]["message"]; t=(m.get("content") or "")+(m.get("reasoning_content") or "")
if not t: print(f"  req{i} EMPTY"); raise SystemExit
run=mx=1; prev=""
for c in t:
    run=run+1 if c==prev else 1; mx=max(mx,run); prev=c
bad=(mx>200 or len(set(t))<12)
print(f"  req{i} {'DEGENERATE' if bad else 'ok'} len={len(t)} maxrun={mx} uniq={len(set(t))}"+(f"  top={collections.Counter(t).most_common(2)}" if bad else ""))
PY
done; }
run(){ local n=$1 model=$2; shift 2; echo "### $n : $(basename $model) : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  setsid nohup $B -m $model -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$n.log 2>&1 < /dev/null &
  for i in $(seq 1 120); do
    grep -q GGML_ASSERT $OUT/srv_$n.log 2>/dev/null && { echo "  HARD ABORT"; grep -m1 GGML_ASSERT $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; grep -m3 -E "error|unknown|unsupported|requires" $OUT/srv_$n.log|tail -3|sed 's/^/       /'; echo; return; }
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null | grep -q choices && { probe "$n"; echo; return; }
    sleep 4
  done; echo "  READY TIMEOUT"; tail -3 $OUT/srv_$n.log|sed 's/^/       /'; echo; }

# 4B first -- cheap, and it is the matched-pair model
run U_A $M  -fa on -ctk f16  -ctv f16     # control: does upstream run this model at all?
run U_B $M  -fa on -ctk q8_0 -ctv q8_0    # THE TEST
run U_C $M  -fa on -ctk q4_0 -ctv q4_0
# then the original 27B, to match RESULT_XFORK exactly
run U_D $M2 -fa on -ctk f16  -ctv f16
run U_E $M2 -fa on -ctk q8_0 -ctv q8_0    # THE TEST, original model
pkill -x llama-server 2>/dev/null; echo "### UPSTREAM TEST DONE $(date -Is)"
