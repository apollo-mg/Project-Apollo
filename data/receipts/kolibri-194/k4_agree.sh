#!/usr/bin/env bash
# K4/K4b on .194 (detached): port 1 = Hob-forge build, port 2 = Eliasfpv28 build; same GGUF; base logits from port 1.
OUT=~/sbench/runs_k4; mkdir -p $OUT; L=$OUT/run.log; log() { echo "$(date '+%F %T') $*" >> $L; }
P1=~/k194/llama.cpp/build_sm60/bin; P2=~/k194/port2/llama.cpp/build_sm60/bin
M=~/AI/Models/kolibri/Kolibri-1-Q4_K_M.gguf; W=~/wikitext-2-raw/wiki.test.raw
FL="-ngl 99 -sm layer -fa on -fit off"
for ctx in 512 2048; do
  if [ $ctx = 512 ]; then CH="-c 512 -b 512 --chunks 16"; else CH="-c 2048 -b 2048 --chunks 8"; fi
  B=$OUT/base_p1_c$ctx.bin
  GGML_CUDA_ALLREDUCE=internal $P1/llama-perplexity -m $M $FL $CH -f $W --kl-divergence-base $B > $OUT/p1_c$ctx.txt 2>&1
  log "c$ctx port1: rc=$? $(grep -E 'Final estimate' $OUT/p1_c$ctx.txt | tail -1 | sed 's/.*Final/Final/')"
  GGML_CUDA_ALLREDUCE=internal $P2/llama-perplexity -m $M $FL $CH -f $W --kl-divergence-base $B --kl-divergence > $OUT/p2_c$ctx.txt 2>&1
  rc=$?; log "c$ctx port2 vs port1: rc=$rc $(grep -E 'Mean +PPL|Mean +KLD|Same top p|Maximum KLD|99.9% +KLD' $OUT/p2_c$ctx.txt | tr -s ' ' | tr '\n' '|' | cut -c1-400)"
  [ $rc != 0 ] && log "port2 error: $(grep -i -E 'error|failed|exception|key not found|missing' $OUT/p2_c$ctx.txt | head -3 | tr '\n' ' ' | cut -c1-300)"
done
log K4_DONE
