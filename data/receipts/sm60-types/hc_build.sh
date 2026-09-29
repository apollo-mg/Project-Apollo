#!/usr/bin/env bash
# PREREG_HC_Q8.md step 1, run ON .194: a patched copy of test-backend-ops with fn_hc_cases.inc (-> ~/test-backend-ops-hc),
# the source tree restored, then llama-perplexity. The fleet libraries' md5 is printed before and after.
set -euo pipefail
cd ~/buun-0b278
git diff --quiet tests/test-backend-ops.cpp
md5sum build_sm60/bin/libggml-cuda.so.0.24.0 | cut -c1-12
cp /tmp/fn_hc_cases.inc tests/fn_hc_cases.inc
L=$(grep -n '^static std::vector<std::unique_ptr<test_case>> make_test_cases_perf() {' tests/test-backend-ops.cpp | cut -d: -f1)
sed -i "$((L+1))a #include \"fn_hc_cases.inc\"" tests/test-backend-ops.cpp
cmake --build build_sm60 --target test-backend-ops -j 40 | tail -1
cp build_sm60/bin/test-backend-ops ~/test-backend-ops-hc
git checkout tests/test-backend-ops.cpp && rm tests/fn_hc_cases.inc
cmake --build build_sm60 --target test-backend-ops llama-perplexity -j 40 | tail -1
md5sum build_sm60/bin/libggml-cuda.so.0.24.0 | cut -c1-12
git status --porcelain | head -3
echo BUILD_OK
