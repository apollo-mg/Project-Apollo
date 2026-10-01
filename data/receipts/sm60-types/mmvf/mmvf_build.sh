#!/usr/bin/env bash
# PREREG_MMVF_SHORTROW.md, run ON .73: static test-backend-ops with the extra cases, from a clean archive of buun
# ab22bc538. Base binary first, then the tuning patch on top (incremental rebuild of mmvf.cu only).
# Launch: setsid nohup bash ~/mmvf/mmvf_build.sh > ~/mmvf/build.log 2>&1 < /dev/null & echo $! > ~/mmvf/build.pid
set -euo pipefail
W=~/mmvf; S=$W/src
rm -rf "$S"; mkdir -p "$S"; tar -xf $W/buun-ab22bc538.tar -C "$S"; cd "$S"
cp $W/mmvf_eval_cases.inc $W/mmvf_perf_cases.inc tests/
T=tests/test-backend-ops.cpp
L=$(grep -n '^static std::vector<std::unique_ptr<test_case>> make_test_cases_perf() {' $T | cut -d: -f1)
sed -i "$((L+1))a #include \"mmvf_perf_cases.inc\"" $T
L=$(grep -n '^static std::vector<std::unique_ptr<test_case>> make_test_cases_eval() {' $T | cut -d: -f1)
sed -i "$((L+1))a #include \"mmvf_eval_cases.inc\"" $T
grep -c 'mmvf_.*_cases.inc' $T
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_CUDA_NCCL=OFF -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_SERVER=OFF > $W/cmake.log 2>&1
date; cmake --build build --target test-backend-ops -j 6 2>&1 | tail -3; date
cp build/bin/test-backend-ops $W/tbo-base
patch -p1 < $W/mmvf_tune.patch
date; cmake --build build --target test-backend-ops -j 6 2>&1 | tail -3; date
cp build/bin/test-backend-ops $W/tbo-tune
sha256sum $W/tbo-base $W/tbo-tune
echo BUILD_OK
