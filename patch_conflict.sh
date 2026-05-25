#!/bin/bash
cd /mnt/TG_2TB/Projects/Apollo/engines/llama_cpp_turboquant
git checkout --ours common/arg.cpp
git checkout --ours ggml/src/ggml-metal/ggml-metal-ops.cpp
git checkout --ours ggml/src/ggml-vulkan/ggml-vulkan.cpp
