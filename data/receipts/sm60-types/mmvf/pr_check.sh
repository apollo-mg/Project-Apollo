#!/usr/bin/env bash
# PR pre-check ON .194: static test-backend-ops from clean buun 082b72c5e (base), then + the PR commit (pr).
# Eval: MUL_MAT/MUL_MAT_ID/MUL_MAT_VEC_FUSION float cases on both. Perf: the registered mmvf perf cases (perf list
# short-circuited as in Deviation 1 -- check build only, not part of the PR).
set -uo pipefail
W=~/mmvf_pr; S=$W/src; mkdir -p $W/out
echo $$ > /tmp/apollo-busy.mmvf-pr; trap 'rm -f /tmp/apollo-busy.mmvf-pr' EXIT
rm -rf "$S"; mkdir -p "$S"; tar -xf $W/buun-082b72c5e.tar -C "$S"; cd "$S"
cp $W/mmvf_perf_cases.inc tests/
T=tests/test-backend-ops.cpp
L=$(grep -n '^static std::vector<std::unique_ptr<test_case>> make_test_cases_perf() {' $T | cut -d: -f1)
sed -i "$((L+1))a #include \"mmvf_perf_cases.inc\"\n    return test_cases; // check build only" $T
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_CUDA_NCCL=OFF -DLLAMA_CURL=OFF > $W/cmake.log 2>&1
cmake --build build --target test-backend-ops -j 36 2>&1 | tail -1; cp build/bin/test-backend-ops $W/tbo-base
patch -p1 < $W/mmvf_pr_e5b433868.patch || { echo PATCH_FAILED; exit 1; }
cmake --build build --target test-backend-ops -j 36 2>&1 | tail -1; cp build/bin/test-backend-ops $W/tbo-pr
cd $W && sha256sum tbo-base tbo-pr
for b in base pr; do
  CUDA_VISIBLE_DEVICES=0 ./tbo-$b test -b CUDA0 -o MUL_MAT,MUL_MAT_ID,MUL_MAT_VEC_FUSION -p 'type(_a)?=(f16|bf16|f32),' -j 8 > out/test_$b.txt 2> out/test_$b.err
  echo "test $b: $(grep 'tests passed' out/test_$b.txt)"
done
for rep in 1 2 3; do for b in base pr; do
  CUDA_VISIBLE_DEVICES=0 ./tbo-$b perf -b CUDA0 -o MUL_MAT > out/perf_${b}_r$rep.txt 2> /dev/null
done; done
echo PRCHECK_DONE
