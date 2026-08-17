#!/usr/bin/env bash
# RDNA4 KV ladder -- where does the 9070 XT stand on the two KV bugs found on sm_60?
#
# Binary: TheTom/llama-cpp-turboquant @ f050a2501 (the PR #295 fix commit), HIP build.
# .73 ran f6124e9 (the #295 MERGE commit) on CUDA sm_60. Same fork, same PR, so this is
# an ARCHITECTURE comparison, not a fork comparison.
#
# Model: Qwen3.5-9B-Q8_0, D=256, 16 heads / 4 KV (GQA 4:1). D=256 is the head dim where
# the collapse lives on sm_60. GQA 4:1 is below Tom's 6:1 gate, so TURBO_AUTO_ASYMMETRIC
# cannot fire regardless; pinned to 0 anyway.
#
# STRUCTURAL LIMIT: one GPU, so there is no tensor split. RESULT_D128.md established the
# ABORT requires -sm tensor, so this ladder CANNOT test the abort at all. It tests the
# COLLAPSE, which is split-independent and therefore fully in scope.
set -u
B=/mnt/TG_2TB/AI/tq295/src/build/bin/llama-server
M=/mnt/TG_2TB/AI/Models/qwen35/plain-Q8_0.gguf
PORT=8095; OUT=$HOME/xfork_rdna4; mkdir -p $OUT
[ -x "$B" ] || { echo "FATAL: no binary"; exit 1; }
[ -f "$M" ] || { echo "FATAL: no model"; exit 1; }
echo "### RDNA4 KV LADDER $(date -Is)"
echo "### binary : $($B --version 2>&1 | head -1)"
echo "### device : $($B --list-devices 2>&1 | grep ROCm)"
echo "### model  : $M"
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
    pgrep -x llama-server >/dev/null || { echo "  SERVER DIED"; grep -m2 -E "E .*(requires|failed|error|support)" $OUT/srv_$n.log|sed 's/^/       /'; echo; return; }
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null | grep -q choices && { probe "$n"; echo; return; }
    sleep 4
  done; echo "  READY TIMEOUT"; tail -3 $OUT/srv_$n.log|sed 's/^/       /'; echo; }
run R0 -ctk f16    -ctv f16       # control
run R1 -ctk q8_0   -ctv q8_0      # THE TEST -- collapses on sm_60 at D=256
run R2 -ctk q4_0   -ctv q4_0      # second stock codec
run R3 -ctk q8_0   -ctv f16       # single-sided, clean on sm_60
run R4 -ctk f16    -ctv q8_0      # single-sided, clean on sm_60
run R5 -ctk q8_0   -ctv q4_0      # mixed stock -- ABORTS on sm_60 under tensor split
run R6 -ctk turbo3 -ctv turbo3    # turbo symmetric -- ABORTS on sm_60 under tensor split
run R7 -ctk iq4_nl -ctv iq4_nl    # ABORTS on sm_60 under tensor split
pkill -x llama-server 2>/dev/null; echo "### RDNA4 LADDER DONE $(date -Is)"
