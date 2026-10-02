#!/usr/bin/env bash
# PREREG_MMVF_SHORTROW.md B5/B6, ON .194: static llama-server + llama-perplexity from a clean archive of buun
# ab22bc538, base first, then mmvf_final.patch (incremental). Binaries -> ~/mmvf/{base,final}/.
set -euo pipefail
W=~/mmvf; S=$W/src
echo $$ > /tmp/apollo-busy.mmvf-build; trap 'rm -f /tmp/apollo-busy.mmvf-build' EXIT
rm -rf "$S"; mkdir -p "$S" $W/base $W/final; tar -xf $W/buun-ab22bc538.tar -C "$S"; cd "$S"
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_CUDA_NCCL=OFF -DLLAMA_CURL=OFF \
  > $W/cmake.log 2>&1
date; cmake --build build --target llama-server llama-perplexity -j 36 2>&1 | tail -2; date
cp build/bin/llama-server build/bin/llama-perplexity $W/base/
patch -p1 < $W/mmvf_final.patch
date; cmake --build build --target llama-server llama-perplexity -j 36 2>&1 | tail -2; date
cp build/bin/llama-server build/bin/llama-perplexity $W/final/
cd $W && sha256sum base/* final/*
echo BUILD_OK
