#!/usr/bin/env bash
# Closes the two remaining gaps in the upstream comparison.
#
# GAP 1 (split asymmetry): kv_upstream.sh ran LAYER split because I assumed upstream had
#   no -sm tensor. The fork's 4B arms ran TENSOR. M1/M2 run the FORK at LAYER so the 4B
#   comparison is matched. (For the 27B this was already closed -- kv_xfork T9 and kv_fa F2
#   both collapse 3/3 under layer on the fork.)
#
# GAP 2 (the abort was never tested upstream): upstream DOES support -sm tensor
#   ({none,layer,row,tensor}). So every abort arm can be asked of upstream directly.
#   S1-S5 do that. Until now "upstream is clean" covered only the collapse.
set -u
FORK=~/llama-cpp-turboquant/build/bin/llama-server
UP=~/llama_upstream/build/bin/llama-server
M4=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8094; OUT=~/xfork_final; mkdir -p $OUT
echo "### FINAL GAP-CLOSER $(date -Is)"
echo "### fork    : $($FORK --version 2>&1 | head -1)"
echo "### upstream: $($UP --version 2>&1 | head -1)"
echo
port_free(){ for i in $(seq 1 40); do pgrep -x llama-server >/dev/null && { sleep 2; continue; }
  (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null && { exec 3<&- 3>&-; sleep 2; continue; }; return 0; done; return 1; }
run(){ local n=$1 bin=$2 tag=$3; shift 3; echo "### $n [$tag] : $*"
  pkill -x llama-server 2>/dev/null; sleep 3; port_free
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup $bin -m $M4 -ngl 99 -c 16384 --jinja --host 127.0.0.1 --port $PORT "$@" > $OUT/srv_$n.log 2>&1 < /dev/null &
  for i in $(seq 1 100); do
    grep -q GGML_ASSERT $OUT/srv_$n.log 2>/dev/null && { echo "  HARD ABORT"; grep -m1 GGML_ASSERT $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; grep -m2 -E "E .*(requires|failed|error|support)" $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
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

echo "--- GAP 1: fork at LAYER split, matching upstream's U_A/U_B ---"
run M1 $FORK FORK -sm layer -fa on -ctk f16  -ctv f16
run M2 $FORK FORK -sm layer -fa on -ctk q8_0 -ctv q8_0

echo "--- GAP 2: upstream under TENSOR split -- the abort arms, never asked of upstream ---"
run S1 $UP UPSTREAM -sm tensor -ts 1,1 -fa on -ctk f16    -ctv f16      # control
run S2 $UP UPSTREAM -sm tensor -ts 1,1 -fa on -ctk q8_0   -ctv q8_0     # collapses on both forks
run S3 $UP UPSTREAM -sm tensor -ts 1,1 -fa on -ctk q8_0   -ctv q4_0     # ABORTS on Tom
run S4 $UP UPSTREAM -sm tensor -ts 1,1 -fa on -ctk iq4_nl -ctv iq4_nl   # ABORTS on Tom
run S5 $UP UPSTREAM -sm tensor -ts 1,1 -fa on -ctk q5_1   -ctv q5_1     # ABORTS on Tom
pkill -x llama-server 2>/dev/null; echo "### FINAL DONE $(date -Is)"
