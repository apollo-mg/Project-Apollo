#!/usr/bin/env bash
# Upstream llama.cpp b12063 (2026-11-03) for the P100s: DeepSeek-V4.1-Flash support merged in #31086 (10-26); ISTA's card
# needs b11870+. A new worktree off ~/llama.cpp-upstream, configured like ~/llama.cpp-beam/build_sm60 (sm_60, gcc-13 host
# compiler for CUDA 12.4, FA on, sched copies 4). Writes its own PID first; last log line BUILD_OK or the error.
# Usage (on .194): build_b12063_sm60.sh    log: ~/llama.cpp-b12063.build.log
echo $$ > ~/llama.cpp-b12063.build.pid
set -euo pipefail
TAG=b12063 SRC=~/llama.cpp-upstream DST=~/llama.cpp-b12063
git -C "$SRC" fetch -q origin "refs/tags/$TAG:refs/tags/$TAG"
[ -d "$DST" ] || git -C "$SRC" worktree add -q --detach "$DST" "$TAG"
cd "$DST"
echo "commit $(git rev-parse HEAD) tag $(git describe --tags)"
cmake -B build_sm60 -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=OFF > /dev/null
cmake --build build_sm60 -j 32 --target llama-server llama-cli llama-perplexity
sha256sum build_sm60/bin/llama-server
echo BUILD_OK
