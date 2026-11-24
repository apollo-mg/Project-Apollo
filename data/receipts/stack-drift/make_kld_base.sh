#!/bin/bash
# PREREG_STACK_DRIFT: the CPU reference. Build 33aeb17f8 for CPU in the desktop worktree, then write the KLD base
# (Qwen3.5-9B Q8_0, wikitext-2 test, -c 512, 10 chunks). The base file stays out of git (several GB).
set -u
R=/mnt/TG_2TB/Projects/Apollo; H=$R/data/receipts/stack-drift; W=$R/engines/rocm10/up_33aeb17f; S=$H/raw/state_drift_cpu.log
log() { echo "$* $(date '+%F %T')" >> $S; }
cd $W && cmake -B build_cpu -DGGML_HIP=OFF -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF > $H/raw/build_cpu.log 2>&1 \
  && cmake --build build_cpu -j 8 --target llama-perplexity llama-server >> $H/raw/build_cpu.log 2>&1; log "cpu build rc=$? $(build_cpu/bin/llama-server --version 2>&1 | grep -o 'commit [0-9a-f]*')"
build_cpu/bin/llama-perplexity -m /mnt/TG_2TB/AI/Models/sci-distill-gguf/Qwen3.5-9B-Q8_0.gguf -f /mnt/TG_2TB/AI/kld/wikitext-2-raw/wiki.test.raw \
  --kl-divergence-base $H/raw/kld_base.bin -c 512 --chunks 10 -ngl 0 -t 8 > $H/raw/kld_base_cpu.log 2>&1
log "kld base rc=$? $(du -h $H/raw/kld_base.bin | cut -f1) $(grep -o 'Final estimate: PPL = [0-9.]*' $H/raw/kld_base_cpu.log)"
log CPU_DONE
