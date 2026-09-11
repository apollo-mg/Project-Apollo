#!/usr/bin/env bash
# Recovered 2026-09-11 from the session transcript -- the original lived in the scratchpad and was lost.
set -u
S=/tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad
OUT=/mnt/TG_2TB/Projects/Apollo/data/receipts/viability/master-ab
mkdir -p "$OUT"
OLDR=/mnt/TG_2TB/Projects/Apollo/engines/buun-llama-cpp
NEWR=/mnt/TG_2TB/Projects/buun-master
OLDB=$OLDR/build_rocm/bin/llama-server
NEWB=$NEWR/build_rocm/bin/llama-server
M=/mnt/TG_2TB/AI/Models/gsq-rco/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf
BENCH=/home/mark/projects/hermes-bench-tool-call
PY=$BENCH/.venv/bin/python
LOG=$OUT/driver.log; : > "$LOG"
say(){ echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
TASK_ARGS=(); while read -r t; do [ -n "$t" ] && TASK_ARGS+=(--task "$t"); done < "$S/latch_tasks.txt"

say "### building origin/master in a separate worktree ###"
if [ ! -d "$NEWR" ]; then
  git -C "$OLDR" worktree add --detach "$NEWR" origin/master >> "$LOG" 2>&1 || { say "worktree failed"; exit 1; }
fi
say "worktree at $(git -C "$NEWR" rev-parse --short HEAD)"
cmake -S "$NEWR" -B "$NEWR/build_rocm" -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 \
      -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=ON >> "$LOG" 2>&1 || { say "cmake configure FAILED"; exit 1; }
say "configured; compiling (this is the long part)"
cmake --build "$NEWR/build_rocm" -j 12 --target llama-server >> "$LOG" 2>&1 || { say "BUILD FAILED"; exit 1; }
say "llama-server built"
cmake --build "$NEWR/build_rocm" -j 12 --target test-cuda-tcq-asym-codebooks >> "$LOG" 2>&1 \
  && say "codebook test built" || say "codebook test target not present / failed to build"

say "### P-M2: buun's own codebook test on gfx1201 ###"
T=$(find "$NEWR/build_rocm" -name 'test-cuda-tcq-asym-codebooks' -type f -executable 2>/dev/null | head -1)
if [ -n "$T" ]; then
  timeout 900 "$T" > "$OUT/codebook_test.log" 2>&1
  say "  codebook test exit=$? (see codebook_test.log)"
  tail -5 "$OUT/codebook_test.log" | sed 's/^/    /' | tee -a "$LOG"
else
  say "  codebook test binary not found"
fi

cleanup(){
  for p in $(pgrep -f '[r]un_agent.py'); do kill -9 "$p" 2>/dev/null; done
  for p in $(pgrep -x llama-server); do kill -TERM "$p" 2>/dev/null; done
  for i in $(seq 1 40); do pgrep -x llama-server >/dev/null || break; sleep 1; done
}
watch_latch(){
  local rd="$1" bp="$2" tag="$3"
  while kill -0 "$bp" 2>/dev/null; do
    sleep 20
    local seq; seq=$($PY - "$rd" <<'PY' 2>/dev/null
import json,glob,os,sys
rows=[]
for f in glob.glob(sys.argv[1]+'/*.json'):
    if os.path.basename(f)=='summary.json': continue
    try: rows.append((os.path.getmtime(f), json.load(open(f)).get('status')))
    except Exception: pass
rows.sort(); print(''.join('I' if s=='INFRA_ERROR' else '.' for _,s in rows))
PY
)
    case "$seq" in *III*) say "  [$tag] LATCH after ${#seq} tasks ($seq) -- aborting early"
        kill -TERM "$bp" 2>/dev/null; sleep 3
        for p in $(pgrep -f '[r]un_agent.py'); do kill -9 "$p" 2>/dev/null; done; return 0;; esac
  done
}
run_one(){
  local which="$1" rep="$2" tag="${which}${rep}"
  local B; [ "$which" = OLD ] && B=$OLDB || B=$NEWB
  say "=== RUN $tag : $which build : $B ==="
  cleanup
  setsid nohup stdbuf -oL -eL "$B" -m "$M" -ngl 99 -c 32768 -np 1 -fa on --kv-unified \
      -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto -n 4096 \
      --reasoning-effort medium --min-p 0 --jinja \
      --host 127.0.0.1 --port 8090 > "$OUT/server_$tag.log" 2>&1 < /dev/null &
  local ok=0
  for i in $(seq 1 150); do
    curl -s -m 5 http://127.0.0.1:8090/v1/chat/completions -H 'Content-Type: application/json' \
      -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' 2>/dev/null \
      | grep -q finish_reason && { ok=1; break; }
    sleep 3
  done
  [ $ok -eq 1 ] || { say "  RUN $tag: server never ready"; return 1; }
  cd "$BENCH"; rm -rf "results/mab_$tag" "traces/mab_$tag" 2>/dev/null
  $PY -m hermesbench run --model "GSQ-RCO-iq3xxs-$tag" --base-url http://127.0.0.1:8090/v1 \
      "${TASK_ARGS[@]}" --toolsets all --timeout-overhead 120 --run-id "mab_$tag" >> "$LOG" 2>&1 &
  local bp=$!; watch_latch "$BENCH/results/mab_$tag" "$bp" "$tag" || true; wait "$bp" 2>/dev/null
  say "  RUN $tag complete"
}
say "### interleaved OLD/NEW VBR, 3 reps each ###"
for rep in 1 2 3; do run_one OLD "$rep"; run_one NEW "$rep"; done
cleanup
say "### MASTER A/B COMPLETE ###"
