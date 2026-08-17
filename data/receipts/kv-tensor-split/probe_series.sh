#!/usr/bin/env bash
# Targeted probe with CLEAN builds, replacing the invalidated bisect.
#
# The first bisect reused one build dir across steps; a clean rebuild showed a commit it
# called GOOD actually collapses, so every GOOD in that log is void. The culprit is EARLIER
# than the 2026-07-31 TurboQuant series.
#
# Rather than an 11-step clean-build bisect (~2h), probe the natural boundaries first:
#   9421bd097  2026-03-24  WIP: add TurboQuant KV cache types (turbo3, turbo4)   <- first turbo touch
#   9421bd097^                                                                   <- before any turbo
#   00fda770b  2026-07-31  ggml : port TurboQuant core quant types + CPU kernels
# If 9421bd097^ is clean and 9421bd097 collapses, that one commit is the answer.
set -u
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8098
echo "### SERIES PROBE $(date -Is)"
test_one() {
  local ref=$1 name=$2 dir=~/probe_$2
  local sha=$(git -C ~/tq_bisect rev-parse "$ref" 2>/dev/null)
  echo "### $name  $sha  $(git -C ~/tq_bisect log -1 --format=%s $sha 2>/dev/null | cut -c1-58)"
  rm -rf "$dir"; git -C ~/tq_bisect worktree prune 2>/dev/null
  git -C ~/tq_bisect worktree add --detach "$dir" "$sha" >/dev/null 2>&1 || { echo "  worktree FAILED"; echo; return; }
  cmake -S "$dir" -B "$dir/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DLLAMA_CURL=OFF \
        -DCMAKE_BUILD_TYPE=Release > "$dir/cfg.log" 2>&1 || { echo "  CONFIGURE FAILED"; echo; return; }
  cmake --build "$dir/build" -j 12 --target llama-server > "$dir/build.log" 2>&1 || { echo "  BUILD FAILED"; grep -m3 -i error "$dir/build.log" | sed 's/^/    /'; echo; return; }
  pkill -x llama-server 2>/dev/null; sleep 4
  TURBO_AUTO_ASYMMETRIC=0 setsid nohup "$dir/build/bin/llama-server" -m $M -ngl 99 -c 8192 --jinja \
      --host 127.0.0.1 --port $PORT -sm tensor -ts 1,1 -fa on -ctk q8_0 -ctv q8_0 > "$dir/srv.log" 2>&1 < /dev/null &
  local ok=0
  for i in $(seq 1 90); do
    pgrep -x llama-server >/dev/null || break
    curl -s --max-time 20 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
      -d '{"messages":[{"role":"user","content":"hi"}],"n_predict":8,"cache_prompt":false}' 2>/dev/null | grep -q choices && { ok=1; break; }
    sleep 4
  done
  if [ $ok -ne 1 ]; then echo "  DID NOT SERVE"; grep -m2 -E "error|assert|unknown" "$dir/srv.log" | sed 's/^/    /'; pkill -x llama-server 2>/dev/null; echo; return; fi
  curl -s --max-time 300 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"Explain how a 3-stage CPU pipeline works, with examples."}],"temperature":1.0,"top_p":0.95,"top_k":20,"n_predict":512,"cache_prompt":false}' \
  | python3 -c "
import json,sys,collections
try: d=json.load(sys.stdin)
except Exception: print('  PARSE_FAIL'); raise SystemExit
if 'choices' not in d: print('  ERR'); raise SystemExit
m=d['choices'][0]['message']; t=(m.get('content') or '')+(m.get('reasoning_content') or '')
if not t: print('  EMPTY'); raise SystemExit
run=mx=1; prev=''
for c in t:
    run=run+1 if c==prev else 1; mx=max(mx,run); prev=c
bad=(mx>200 or len(set(t))<12)
print(f\"  ==> {'COLLAPSE' if bad else 'CLEAN'}  len={len(t)} maxrun={mx} uniq={len(set(t))}\")
"
  pkill -x llama-server 2>/dev/null; echo
}
test_one "9421bd097^" before_turbo
test_one "9421bd097"  first_turbo
test_one "00fda770b"  tq_core
pkill -x llama-server 2>/dev/null
echo "### SERIES PROBE DONE $(date -Is)"
