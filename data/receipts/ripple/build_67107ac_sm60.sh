#!/usr/bin/env bash
# Upstream llama.cpp master 67107ac34f (2026-11-06) for the P100s: Ripple support (#31692, fecdc81e) plus its follow-up
# fix (#31683, kv shifting / per-model rope). The release tags did not contain the merge yet (b12144 is 13 behind).
# Same configuration as ../ds41-h2h/build_b12063_sm60.sh. Writes its own PID first; last log line BUILD_OK or the error.
echo $$ > ~/llama.cpp-67107ac.build.pid
set -euo pipefail
C=67107ac34f SRC=~/llama.cpp-upstream DST=~/llama.cpp-67107ac
git -C "$SRC" fetch -q origin master
[ -d "$DST" ] || git -C "$SRC" worktree add -q --detach "$DST" "$C"
cd "$DST"; echo "commit $(git rev-parse HEAD)"
cmake -B build_sm60 -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=60 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-13 \
  -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA_FA=ON -DGGML_SCHED_MAX_COPIES=4 -DLLAMA_BUILD_TESTS=OFF > /dev/null
cmake --build build_sm60 -j 32 --target llama-server llama-cli llama-perplexity
sha256sum build_sm60/bin/llama-server
echo BUILD_OK
