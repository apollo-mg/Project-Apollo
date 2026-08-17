#!/usr/bin/env bash
# VERIFY the bisect verdict with CLEAN build dirs.
#
# The bisect named 2a716ac47 "vulkan/metal/hip : add TurboQuant kernel support" as the
# first bad commit -- but that commit touches ONLY metal/vulkan/hip files, zero CUDA.
# We test on CUDA sm_60. A commit changing no CUDA code should not change CUDA behaviour.
#
# Prime suspect is the harness: bisect_test.sh reused ONE build dir across every step, so
# incremental CMake across large commit jumps may have produced stale/mixed binaries.
# This rebuilds the culprit and its parent from scratch, in separate trees, and re-tests.
set -u
M=~/AI/Models/tqstudy/Qwen3.5-4B-BF16.gguf
PORT=8097
CULPRIT=2a716ac47
PARENT=$(git -C ~/tq_bisect rev-parse ${CULPRIT}^ 2>/dev/null)
echo "### VERIFY $(date -Is)"
echo "### culprit: $CULPRIT  $(git -C ~/tq_bisect log -1 --format=%s $CULPRIT)"
echo "### parent : $PARENT  $(git -C ~/tq_bisect log -1 --format=%s $PARENT)"
echo

test_one() {
  local sha=$1 dir=$2
  echo "### === $sha  ($(git -C ~/tq_bisect log -1 --format=%s $sha | cut -c1-60)) ==="
  rm -rf "$dir"
  git -C ~/tq_bisect worktree remove --force "$dir" 2>/dev/null
  git -C ~/tq_bisect worktree add --detach "$dir" "$sha" > /dev/null 2>&1 || { echo "  worktree FAILED"; return; }
  cmake -S "$dir" -B "$dir/build" -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 \
        -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release > "$dir/cfg.log" 2>&1 || { echo "  CONFIGURE FAILED"; return; }
  cmake --build "$dir/build" -j 12 --target llama-server > "$dir/build.log" 2>&1 || { echo "  BUILD FAILED"; tail -3 "$dir/build.log" | sed 's/^/    /'; return; }
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
  if [ $ok -ne 1 ]; then echo "  SERVER NEVER SERVED"; grep -m2 -E "error|assert" "$dir/srv.log" | sed 's/^/    /'; pkill -x llama-server 2>/dev/null; return; fi
  for r in 1 2; do
    curl -s --max-time 300 "http://127.0.0.1:$PORT/v1/chat/completions" -H "Content-Type: application/json" \
      -d '{"messages":[{"role":"user","content":"Explain how a 3-stage CPU pipeline works, with examples."}],"temperature":1.0,"top_p":0.95,"top_k":20,"n_predict":512,"cache_prompt":false}' \
    | python3 -c "
import json,sys,collections
try: d=json.load(sys.stdin)
except Exception: print('  rep$r PARSE_FAIL'); raise SystemExit
if 'choices' not in d: print('  rep$r ERR'); raise SystemExit
m=d['choices'][0]['message']; t=(m.get('content') or '')+(m.get('reasoning_content') or '')
if not t: print('  rep$r EMPTY'); raise SystemExit
run=mx=1; prev=''
for c in t:
    run=run+1 if c==prev else 1; mx=max(mx,run); prev=c
bad=(mx>200 or len(set(t))<12)
print(f\"  rep$r {'BAD/collapse' if bad else 'GOOD/clean'} len={len(t)} maxrun={mx} uniq={len(set(t))}\"+(f' top={collections.Counter(t).most_common(1)}' if bad else ''))
"
  done
  pkill -x llama-server 2>/dev/null
  echo
}

test_one "$PARENT"  ~/vfy_parent
test_one "$CULPRIT" ~/vfy_culprit
echo "### VERIFY DONE $(date -Is)"
