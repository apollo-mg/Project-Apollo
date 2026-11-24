#!/bin/bash
# PREREG_ROCM10 measures after build_rocm10.sh: B1 smoke on all five builds; B3 same-source M1 replays; B4 speed
# (Deviation 1); B2 test-backend-ops on the three heads last (long). One GPU job at a time; servers by recorded PID.
set -u
R=/mnt/TG_2TB/Projects/Apollo; E=$R/engines; H=$R/data/receipts/stack-drift; QA=$R/data/receipts/quant-abstention
PY=$R/venv_cachyos/bin/python3; PORT=8095; S=$H/raw/state_measures.log; log() { echo "$* $(date '+%F %T')" >> $S; }
Q35=/mnt/TG_2TB/AI/Models/sci-distill-gguf/Qwen3.5-9B-Q8_0.gguf; G41=/mnt/TG_2TB/models_small/gguf/granite-4.1-3b-Q8_0.gguf
WIKI=/mnt/TG_2TB/AI/kld/wikitext-2-raw/wiki.test.raw
up() {  # up WRAP BIN MODEL TAG FLAGS... ; sets SP, returns 0 when healthy
  local W=$1 B=$2 M=$3 T=$4; shift 4
  $W $B/llama-server -m $M "$@" --host 127.0.0.1 --port $PORT > $H/raw/server_$T.log 2>&1 &
  SP=$!; for i in $(seq 120); do curl -s 127.0.0.1:$PORT/health 2>/dev/null | grep -q ok && return 0; kill -0 $SP 2>/dev/null || return 1; sleep 2; done; return 1
}
down() { kill $SP 2>/dev/null; wait $SP 2>/dev/null; }
log "start; $(pacman -Q hip-runtime-amd rocblas | tr '\n' ' ')"
# B1: every build loads Qwen3.5-9B and answers one greedy request
for b in buun_38ada0e1 up_4bc61eed up_33aeb17f buun_1e50db7b tq_f7c3638e; do
  [ -x $E/rocm10/$b/build_rocm/bin/llama-server ] || { log "B1 $b NO BINARY"; continue; }
  if up env $E/rocm10/$b/build_rocm/bin $Q35 b1_$b -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --jinja --cache-ram 0; then
    A=$(curl -s -m 120 127.0.0.1:$PORT/v1/chat/completions -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"What is the capital of Australia? One short sentence."}],"temperature":0,"max_tokens":40,"chat_template_kwargs":{"enable_thinking":false}}' | $PY -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"].strip()[:80])' 2>&1)
    log "B1 $b PASS-LOAD answer: $A"
  else log "B1 $b FAIL (server did not become healthy; see server_b1_$b.log)"; fi
  down
done
# B3: same-source M1 replays on 10.1
if up env $E/rocm10/buun_38ada0e1/build_rocm/bin $G41 FZ_BASE_N10 -ngl 99 -c 4096 -np 1 -ctk f16 -ctv f16 --cache-ram 0; then
  ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm FZ_BASE_N10 --max-tokens 1024 --usage --no-think-check --meta '{"model": "granite-4.1-3b-Q8_0.gguf", "build": "buun 38ada0e1b rebuilt on ROCm 10.1 (engines/rocm10/buun_38ada0e1)", "host": "RX 9070 XT", "prereg": "PREREG_ROCM10.md B3"}' > $H/raw/run_FZ_BASE_N10.log 2>&1 ); log "B3 FZ_BASE_N10 rc=$?"
else log "B3 FZ_BASE_N10 server failed"; fi; down
if up env $E/rocm10/up_4bc61eed/build_rocm/bin $Q35 Q35R_N10 -ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0; then
  ( cd $QA && $PY run_main.py --url http://127.0.0.1:$PORT --arm Q35R_N10 --max-tokens 1024 --usage --meta '{"model": "Qwen3.5-9B-Q8_0.gguf", "sha256": "f904644b...", "commit": "4bc61eed7 rebuilt on ROCm 10.1 (engines/rocm10/up_4bc61eed)", "host": "RX 9070 XT", "prereg": "PREREG_ROCM10.md B3"}' > $H/raw/run_Q35R_N10.log 2>&1 ); log "B3 Q35R_N10 rc=$?"
else log "B3 Q35R_N10 server failed"; fi; down
# B4 (Deviation 1): prompt processing and perplexity, old binary on 7.2.4 vs rebuild on 10.1, alternating, 3 each
for rep in 1 2 3; do
  for side in old new; do
    if [ $side = old ]; then W=$R/tools/rocm724.sh; B=$E/llama_cpp_4bc61eed/build_rocm/bin; else W=env; B=$E/rocm10/up_4bc61eed/build_rocm/bin; fi
    $W $B/llama-perplexity -m $Q35 -f $WIKI -c 512 --chunks 20 -ngl 99 -ctk f16 -ctv f16 > $H/raw/ppl_b4_${side}_$rep.log 2>&1
    log "B4 $side rep $rep rc=$? $(grep -o 'Final estimate: PPL = [0-9.]*' $H/raw/ppl_b4_${side}_$rep.log) | $(grep -o 'prompt eval time = .*' $H/raw/ppl_b4_${side}_$rep.log | head -1 | cut -c1-110)"
  done
done
# B2: test-backend-ops on the three heads (each GPU op against the CPU backend)
for b in up_33aeb17f buun_1e50db7b tq_f7c3638e; do
  T=$E/rocm10/$b/build_rocm/bin/test-backend-ops
  [ -x $T ] || { log "B2 $b NO test-backend-ops"; continue; }
  timeout 5400 $T -b ROCm0 > $H/raw/tbo_$b.log 2>&1; rc=$?
  log "B2 $b rc=$rc $(grep -c -E ' OK$|\[OK\]|: OK' $H/raw/tbo_$b.log) ok-lines, $(grep -c -E 'FAIL' $H/raw/tbo_$b.log) FAIL-lines, last: $(grep -E 'tests passed|Backend|passed' $H/raw/tbo_$b.log | tail -2 | tr '\n' ' ' | cut -c1-160)"
done
log MEASURES_DONE
