#!/usr/bin/env bash
# K5 on .194 (detached): wait for the Q3_K_S download + sha check, then K5a-K5d (k5_compare.py) and K5e (port 2 on
# Q3_K_S, KLD against port 1's saved Q4_K_M base logits from K4).
OUT=~/sbench/runs_k5; L=$OUT/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
P2=~/k194/port2/llama.cpp/build_sm60/bin; K4=~/sbench/runs_k4
A=~/AI/Models/kolibri/Kolibri-1-Q4_K_M.gguf; Q=~/AI/Models/kolibri/Kolibri-1-Q3_K_S.gguf; W=~/wikitext-2-raw/wiki.test.raw
while kill -0 "$(cat $OUT/download.pid)" 2>/dev/null; do sleep 10; done
grep -q 'Kolibri-1-Q3_K_S.gguf: OK' $OUT/download.log || { log "K5: download/sha failed: $(tr '\n' ' ' < $OUT/download.log)"; log K5_DONE; exit 1; }
log "K5: Q3_K_S sha256 OK"
PYTHONPATH=~/k194/port2/llama.cpp/gguf-py ~/strata/.venv/bin/python $OUT/k5_compare.py $A $Q > $OUT/k5_compare.txt 2>&1
log "K5a-d: rc=$? $(grep -E '^K5[a-d]:' $OUT/k5_compare.txt | tr '\n' '|')"
FL="-ngl 99 -sm layer -fa on -fit off"
for ctx in 512 2048; do
  if [ $ctx = 512 ]; then CH="-c 512 -b 512 --chunks 16"; else CH="-c 2048 -b 2048 --chunks 8"; fi
  GGML_CUDA_ALLREDUCE=internal $P2/llama-perplexity -m $Q $FL $CH -f $W --kl-divergence-base $K4/base_p1_c$ctx.bin --kl-divergence > $OUT/q3_c$ctx.txt 2>&1
  rc=$?; log "K5e c$ctx Q3_K_S(port2) vs Q4_K_M(port1): rc=$rc $(grep -E 'Mean +PPL|Mean +KLD|Same top p|Maximum KLD|99.9% +KLD|Median +KLD' $OUT/q3_c$ctx.txt | tr -s ' ' | tr '\n' '|' | cut -c1-500)"
  [ $rc != 0 ] && log "K5e error: $(grep -i -E 'error|failed|exception|mismatch|inconsistent' $OUT/q3_c$ctx.txt | head -3 | tr '\n' ' ' | cut -c1-300)"
done
log K5_DONE
