#!/usr/bin/env bash
# Final PR check ON .194: clean buun 082b72c5e + mmvf_pr_final.patch exactly as submitted (no harness edits).
# Eval: float MUL_MAT/MUL_MAT_ID/MUL_MAT_VEC_FUSION; perf: the PR's own 7 cases via -p, stock perf list intact.
set -uo pipefail
W=~/mmvf_pr; S=$W/src_final
echo $$ > /tmp/apollo-busy.mmvf-pr; trap 'rm -f /tmp/apollo-busy.mmvf-pr' EXIT
rm -rf "$S"; mkdir -p "$S"; tar -xf $W/buun-082b72c5e.tar -C "$S"; cd "$S"
patch -p1 < $W/mmvf_pr_final.patch || { echo PATCH_FAILED; exit 1; }
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_CUDA_NCCL=OFF -DLLAMA_CURL=OFF > $W/cmake_final.log 2>&1
cmake --build build --target test-backend-ops -j 36 2>&1 | tail -1
cp build/bin/test-backend-ops $W/tbo-final-pr; cd $W
CUDA_VISIBLE_DEVICES=0 ./tbo-final-pr test -b CUDA0 -o MUL_MAT,MUL_MAT_ID,MUL_MAT_VEC_FUSION -p 'type(_a)?=(f16|bf16|f32),' -j 8 > out/test_final_pr.txt 2>&1
echo "test final-pr: $(grep 'tests passed' out/test_final_pr.txt)"
CUDA_VISIBLE_DEVICES=0 ./tbo-final-pr perf -b CUDA0 -o MUL_MAT -p 'm=(10240|4096|32000|8192),n=(1|2|8),k=(320|448|192|640|4096),bs=\[1,1\],nr=\[1,1\]' > out/perf_final_pr.txt 2> out/perf_final_pr.err
echo "perf rc=$? cases=$(grep -c 'us/run' out/perf_final_pr.txt) abort=$(grep -c 'GGML_ASSERT' out/perf_final_pr.err)"
echo FINALCHECK_DONE
