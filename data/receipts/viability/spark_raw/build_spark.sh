#!/usr/bin/env bash
# Build XHToken/llama.cpp (spark2_5 arch) for gfx1201. Their README claims CPU+CUDA only,
# but the fork adds nothing under ggml/ -- 541 lines, all graph-building on existing ops --
# so HIP should work. This tests that.
set -u
cd /tmp/claude-1000/-mnt-TG-2TB-Projects-Apollo/9457b3f4-5754-4ef0-902f-d30c8f5f3912/scratchpad/spark-llama
cmake -S . -B build_rocm -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release > /tmp/spark_cmake.log 2>&1
echo "cmake rc=$?"
cmake --build build_rocm --target llama-server llama-cli -j 12 2>&1 | tail -8
echo "######## SPARK BUILD DONE $(date -Iseconds)"
