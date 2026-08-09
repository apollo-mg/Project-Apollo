#!/usr/bin/env bash
# TCQ leg 3 — the margin bench. buun's turbo3_tcq vs TheTom's turbo3, task-grounded
# logprob distance-to-flip on the shared rd_*_c2 routing cases.
#
# Legs 1 (KLD) and 2 (hazard/bench) are published; this is the third leg buun asked for on
# 2026-07-07 and it has never run. Pre-flight (2026-08-08) established: both builds are
# byte-deterministic at temp 0 under -np 1 + --no-cache-prompt, and the task is SATURATED at
# argmax (5/5 exact on every arm, identical text across f16/turbo3/turbo3_tcq) — so accuracy
# is blind here and the logprob margins are the entire signal.
#
# DECLARED BUILD DELTA: buun's side runs buun_tree_current (master 02f8581c6), NOT the
# 2026-07-06 tree that produced legs 1-2. Reason: the old tree carries 38859deff's OOB write
# in ggml_cuda_argmax that fires on every greedy/temp<=0 sample. Tom's build has no such code
# path (91-line argmax.cu, single dst[row] write), so keeping the old tree would have put a
# memory-corruption bug on buun's side ONLY. Verified: all 197 shared tcq/codebook sources are
# byte-identical between the two trees, so the CODEC under test is unchanged.
set -u
D=/home/mark/leg3
OUT=$D/results
MODEL=/home/mark/AI/Models/Qwopus-Coder/Qwopus3.6-27B-Coder-heretic-Q6_K.gguf
PORT=8099
mkdir -p "$OUT"

# label bin ktype
run_arm() {
  local label=$1 bin=$2 ktype=$3 tier=$4 ctx=$5
  echo "########## ARM $label  (-ctk/-ctv $ktype)  $(date +%H:%M:%S)"
  pkill -x llama-server 2>/dev/null; sleep 5
  TURBO_AUTO_ASYMMETRIC=0 "$bin" -m "$MODEL" -c "$ctx" -ngl 99 -sm layer -np 1 \
    --no-cache-prompt --cache-ram 0 -ctk "$ktype" -ctv "$ktype" \
    --host 127.0.0.1 --port $PORT > "$OUT/${label}_server.log" 2>&1 &
  for i in $(seq 1 120); do curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 5; done
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 || {
    echo "FATAL: $label never ready"; tail -20 "$OUT/${label}_server.log"; return 1; }

  # A silent K-type upgrade would make this a different measurement (the run-1 post-mortem
  # from the KV-depth leg). env=0 is set; verify nothing overrode it.
  if grep -qai "auto.asymmetric\|SUBST" "$OUT/${label}_server.log"; then
    echo "!! WARNING $label: asymmetric/substitution notice in boot log"
    grep -ai "auto.asymmetric\|SUBST" "$OUT/${label}_server.log" | head -3
  fi
  # G-L3a: the prompt cache MUST be off. --no-cache-prompt alone is a per-REQUEST default in
  # these builds; the server-side reusable cache is separate and defaults to 8192 MiB. A warm
  # prefix changes batch shape -> reduction order -> logprobs, which IS the measurement here.
  if grep -qa "prompt cache is enabled" "$OUT/${label}_server.log"; then
    echo "FATAL $label: server prompt cache still ENABLED — margins would be contaminated"
    grep -a "prompt cache" "$OUT/${label}_server.log" | head -2
    pkill -x llama-server; return 1
  fi
  echo "  G-L3a prompt cache OFF ✓"
  grep -am1 "TURBO meansub" "$OUT/${label}_server.log" || echo "  (no TURBO meansub line — Tom's build does not print one)"

  echo "--- $label tier $tier  ctx=$ctx  ($(date +%H:%M:%S))"
  # probe_router is resumable by case id; a killed run continues where it stopped.
  python3 "$D/probe_router.py" --base-url "http://127.0.0.1:$PORT/v1" --model local \
    --data "$D/cases/rd_${tier}_c2.jsonl" --out "$OUT/lp_${label}_${tier}.jsonl" \
    --max-tokens 64 --label "${label}_${tier}" 2>&1 | tail -2
  pkill -x llama-server 2>/dev/null; sleep 5
  echo "=== $label DONE $(date +%H:%M:%S)"
}

echo "===== LEG 3 MARGIN BENCH START $(date -Iseconds) ====="
nvidia-smi --query-gpu=index,clocks.sm,power.limit --format=csv,noheader > "$OUT/clocks.txt"
cat "$OUT/clocks.txt"

TIER=${1:?usage: leg3_run.sh <tier> <ctx>}
CTX=${2:?usage: leg3_run.sh <tier> <ctx>}
run_arm TOM  /home/mark/llama-cpp-turboquant/build/bin/llama-server  turbo3      "$TIER" "$CTX"
run_arm BUUN /home/mark/buun_tree_current/build/bin/llama-server     turbo3_tcq  "$TIER" "$CTX"

echo "===== LEG 3 DONE $(date -Iseconds) ====="
wc -l "$OUT"/lp_*.jsonl
