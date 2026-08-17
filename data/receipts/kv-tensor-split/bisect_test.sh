#!/usr/bin/env bash
# git bisect run script: does THIS commit of TheTom/llama-cpp-turboquant collapse?
#
#   exit 0  = GOOD (clean output)
#   exit 1  = BAD  (512-char single-token collapse)
#   exit 125 = SKIP (cannot build / cannot run -> untestable commit)
#
# Test: Qwen3.5-4B-BF16 (D=256, GQA 4:1, no MTP), -sm tensor -ts 1,1, q8_0 K+V.
# Chosen because it is small (fast load), collapses reliably at fork HEAD (kv_4b.sh Q2
# 3/3), and is clean on upstream (kv_final.sh S2 3/3) -- so the endpoints are known.
set -u
SRC=~/tq_bisect
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8096
cd "$SRC" || exit 125

echo "### $(git log -1 --format='%h %ad %s' --date=short)" >&2

cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DLLAMA_CURL=OFF \
      -DCMAKE_BUILD_TYPE=Release > /tmp/bisect_cfg.log 2>&1 || { echo "  SKIP: configure failed" >&2; exit 125; }
cmake --build build --config Release -j 12 --target llama-server > /tmp/bisect_build.log 2>&1 || {
    echo "  SKIP: build failed" >&2; exit 125; }

pkill -x llama-server 2>/dev/null; sleep 4
TURBO_AUTO_ASYMMETRIC=0 setsid nohup ./build/bin/llama-server -m $M -ngl 99 -c 8192 --jinja \
    --host 127.0.0.1 --port $PORT -sm tensor -ts 1,1 -fa on -ctk q8_0 -ctv q8_0 \
    > /tmp/bisect_srv.log 2>&1 < /dev/null &

ok=0
for i in $(seq 1 90); do
    pgrep -x llama-server >/dev/null || break
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
        -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null \
        | grep -q '"choices"' && { ok=1; break; }
    sleep 4
done
[ $ok -eq 1 ] || { pkill -x llama-server 2>/dev/null; echo "  SKIP: server never served" >&2; exit 125; }

verdict=$(curl -s --max-time 300 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Explain how a 3-stage CPU pipeline works, with examples."}],"temperature":1.0,"top_p":0.95,"top_k":20,"n_predict":512,"cache_prompt":false}' \
  | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('SKIP'); raise SystemExit
if 'choices' not in d: print('SKIP'); raise SystemExit
m=d['choices'][0]['message']; t=(m.get('content') or '')+(m.get('reasoning_content') or '')
if not t: print('SKIP'); raise SystemExit
run=mx=1; prev=''
for c in t:
    run=run+1 if c==prev else 1; mx=max(mx,run); prev=c
print('BAD' if (mx>200 or len(set(t))<12) else 'GOOD')
")
pkill -x llama-server 2>/dev/null
echo "  verdict: $verdict" >&2
case "$verdict" in
  GOOD) exit 0 ;;
  BAD)  exit 1 ;;
  *)    exit 125 ;;
esac
