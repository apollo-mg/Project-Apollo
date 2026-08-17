#!/usr/bin/env bash
# Close the split-mode asymmetry in the upstream comparison.
#
# Upstream has no -sm tensor, so kv_upstream.sh ran LAYER split. The fork's 4B arms
# (kv_4b.sh Q1-Q3) all ran TENSOR split. For the 27B that gap is already closed --
# kv_xfork T9 and kv_fa F2 both collapse 3/3 under LAYER on the fork -- but for the 4B
# it is not, and the 4B is the matched-pair model the D=256 claim leans on.
#
# One arm: fork binary, 4B, LAYER split, q8_0 K+V. Same split as upstream, same model,
# same node. If it collapses, the upstream-vs-fork comparison is airtight.
set -u
B=~/llama-cpp-turboquant/build/bin/llama-server
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8094; OUT=~/xfork_matched; mkdir -p $OUT
echo "### MATCHED-SPLIT CLOSER $(date -Is)"
echo "### binary: $($B --version 2>&1 | head -1)  [FORK]"
echo
port_free(){ for i in $(seq 1 40); do pgrep -x llama-server >/dev/null && { sleep 2; continue; }
  (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { exec 3<&- 3>&-; sleep 2; continue; }; return 0; done; return 1; }
run(){ local n=$1; shift; echo "### $n : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup $B -m $M -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$n.log 2>&1 < /dev/null &
  for i in $(seq 1 100); do
    grep -q GGML_ASSERT $OUT/srv_$n.log 2>/dev/null && { echo "  HARD ABORT"; echo; return; }
    pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; grep -m2 -E "E .*(requires|failed|error)" $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null | grep -q choices && break
    sleep 4
  done
  for i in 1 2 3; do
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
  done; echo; }
run M1 -sm layer -fa on -ctk f16  -ctv f16    # control, matches upstream U_A
run M2 -sm layer -fa on -ctk q8_0 -ctv q8_0   # THE MATCHED ARM, matches upstream U_B
pkill -x llama-server 2>/dev/null; echo "### MATCHED CLOSER DONE $(date -Is)"
