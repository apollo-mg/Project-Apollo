#!/bin/bash
# PREREG_ROCM10: the five builds on the desktop's system ROCm 10.1, one at a time (8 jobs each, as build_engine.sh).
set -u
R=/mnt/TG_2TB/Projects/Apollo; E=$R/engines; L=$R/data/receipts/stack-drift/raw; S=$L/state_builds.log
log() { echo "$* $(date '+%F %T')" >> $S; }
log "start; $(pacman -Q hip-runtime-amd rocblas rocm-llvm | tr '\n' ' ')"
for spec in "buun_38ada0e1|$E/buun-llama-cpp|38ada0e1b|OFF|llama-bench" \
            "up_4bc61eed|$E/llama_cpp_upstream_f74e2fa|4bc61eed7|OFF|llama-bench" \
            "up_33aeb17f|$E/llama_cpp_upstream_f74e2fa|33aeb17f85869279e3821f746bc645357139bc2c|ON|test-backend-ops llama-bench" \
            "buun_1e50db7b|$E/buun-llama-cpp|1e50db7be8e87d80d660f6ea18e01f2a599ffcba|ON|test-backend-ops llama-bench" \
            "tq_f7c3638e|$E/llama_cpp_turboquant|f7c3638e83ff6ee2c8c1ccd7db642dbe2360eccf|ON|test-backend-ops llama-bench"; do
  IFS='|' read -r NAME SRC REF TESTS EXTRA <<< "$spec"
  SRC=$SRC BUILD_TESTS=$TESTS EXTRA_TARGETS="$EXTRA" bash $R/data/scorecard/build_engine.sh gfx1201 $REF $E/rocm10/$NAME > $L/build_$NAME.log 2>&1
  log "$NAME rc=$? $(tail -1 $L/build_$NAME.log | cut -c1-160)"
done
log BUILDS_DONE
