#!/usr/bin/env bash
# Deviation 1 (harness only): buun ab22bc538's stock perf list aborts in its own constructor
# (test-backend-ops.cpp GGML_ASSERT(!(v_is_view_of_k && v_is_k_view)), a flash-attn case), so perf mode returns
# right after mmvf_perf_cases.inc. Rebuilds tbo-tune (tree is patched), then reverses the patch for tbo-base.
set -euo pipefail
W=~/mmvf; cd $W/src
T=tests/test-backend-ops.cpp
grep -q 'return test_cases; // mmvf: stock perf list aborts' $T || \
  sed -i '/#include "mmvf_perf_cases.inc"/a \    return test_cases; // mmvf: stock perf list aborts at this commit (Deviation 1)' $T
grep -n -A1 'mmvf_perf_cases.inc' $T
patch -p1 --dry-run -R < $W/mmvf_tune.patch > /dev/null   # tree must currently be patched
date; cmake --build build --target test-backend-ops -j 6 2>&1 | tail -1
cp build/bin/test-backend-ops $W/tbo-tune
patch -p1 -R < $W/mmvf_tune.patch
date; cmake --build build --target test-backend-ops -j 6 2>&1 | tail -1; date
cp build/bin/test-backend-ops $W/tbo-base
sha256sum $W/tbo-base $W/tbo-tune
echo REBUILD_OK
