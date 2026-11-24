#!/bin/bash
# PREREG_ROCM10 Deviation 2: rebuild buun head with CMAKE_HIP_ARCHITECTURES set, after B4 finishes; then its B2.
R=/mnt/TG_2TB/Projects/Apollo; E=$R/engines; H=$R/data/receipts/stack-drift; S=$H/raw/state_builds.log
until grep -q "B4 new rep 3" $H/raw/state_measures.log 2>/dev/null; do sleep 30; done
W=$E/rocm10/buun_1e50db7b
cd $W && HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" cmake -B build_rocm -DGGML_HIP=ON -DGPU_TARGETS=gfx1201 \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=ON -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
  > $H/raw/build_buun_1e50db7b_dev2.log 2>&1 && cmake --build build_rocm -j 8 --target llama-server llama-cli llama-perplexity test-backend-ops llama-bench >> $H/raw/build_buun_1e50db7b_dev2.log 2>&1
echo "buun_1e50db7b (Deviation 2) rc=$? $(build_rocm/bin/llama-server --version 2>&1 | grep -m1 -o -E '(commit|version).*') $(date '+%F %T')" >> $S
# the 9070 is busy with the measure chain and then the desktop drift runs; run after both
until grep -q "desk: done" $H/raw/state_orchestrate.log 2>/dev/null; do sleep 60; done
timeout 5400 build_rocm/bin/test-backend-ops -b ROCm0 > $H/raw/tbo_buun_1e50db7b.log 2>&1
echo "B2 buun_1e50db7b (after Deviation 2) rc=$? $(grep -c -E 'FAIL' $H/raw/tbo_buun_1e50db7b.log) FAIL-lines, last: $(grep -E 'tests passed|passed' $H/raw/tbo_buun_1e50db7b.log | tail -2 | tr '\n' ' ' | cut -c1-160) $(date '+%F %T')" >> $H/raw/state_measures.log
