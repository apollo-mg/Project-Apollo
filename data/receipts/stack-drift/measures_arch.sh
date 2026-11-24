#!/bin/bash
# Deviation 3 chain: rebuild buun head (Deviation 2 flag) now; after the desktop drift runs, the measures on Arch's HIP runtime.
R=/mnt/TG_2TB/Projects/Apollo; E=$R/engines; H=$R/data/receipts/stack-drift
W=$E/rocm10/buun_1e50db7b
( cd $W && HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" cmake -B build_rocm -DGGML_HIP=ON -DGPU_TARGETS=gfx1201 \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=ON -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
  > $H/raw/build_buun_1e50db7b_dev2.log 2>&1 && cmake --build build_rocm -j 8 --target llama-server llama-cli llama-perplexity test-backend-ops llama-bench >> $H/raw/build_buun_1e50db7b_dev2.log 2>&1 )
echo "buun_1e50db7b (Deviation 2) rc=$? $($W/build_rocm/bin/llama-server --version 2>&1 | grep -m1 -o -E 'version.*') $(date '+%F %T')" >> $H/raw/state_builds.log
until grep -q "desk: done" $H/raw/state_orchestrate.log 2>/dev/null; do sleep 60; done
WRAPNEW=$R/tools/rocm101arch.sh STATE=state_measures_arch.log SFX=_arch bash $H/run_rocm10.sh
