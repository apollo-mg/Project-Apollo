#!/usr/bin/env bash
# The confound killer for RESULT_D128.md.
#
# That receipt compared Qwen3.8-27B-Q6_K (D=256, GQA 6:1, MTP, 22.9GB) against
# Llama-3.2-3B-BF16 (D=128, GQA 3:1, no MTP, 6.4GB) and concluded the collapse is
# head-dim-dependent -- while admitting arch, GQA, weight format, size and MTP all
# moved at the same time.
#
# Qwen3.5-4B-BF16 is D=256, 16 heads / 4 KV (GQA 4:1), BF16, 8.4GB, no MTP.
# Against the Llama that is: both BF16, both small, both MTP-free, GQA 4:1 vs 3:1.
# Weight format, size, MTP and most of the GQA gap all cancel. What is left is head
# dim and Qwen-vs-Llama architecture.
#
#   Q2 collapses  -> head dim (or Qwen arch) is the variable; D=256 claim gets much stronger
#   Q2 clean      -> head dim is NOT the variable and RESULT_D128.md needs rewriting
set -u
B=~/llama-cpp-turboquant/build/bin/llama-server
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8092; OUT=~/xfork_4b; mkdir -p $OUT
[ -f "$M" ] || { echo "FATAL: no model at $M"; exit 1; }
echo "### 4B D=256 CONFOUND ARM $(date -Is)"
python3 ~/hd.py "$M" | sed 's/^/### geom: /'
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
run(){ local n=$1; shift; echo "### $n : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup $B -m $M -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$n.log 2>&1 < /dev/null &
  for i in $(seq 1 100); do
    grep -q GGML_ASSERT $OUT/srv_$n.log 2>/dev/null && { echo "  HARD ABORT"; grep -m1 GGML_ASSERT $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; grep -m2 -E "E .*(requires|failed|error)" $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null | grep -q choices && { probe "$n"; echo; return; }
    sleep 4
  done; echo "  READY TIMEOUT"; echo; }
run Q1 -sm tensor -ts 1,1 -ctk f16  -ctv f16
run Q2 -sm tensor -ts 1,1 -ctk q8_0 -ctv q8_0
run Q3 -sm tensor -ts 1,1 -ctk q4_0 -ctv q4_0
pkill -x llama-server 2>/dev/null; echo "### 4B ARM DONE $(date -Is)"
