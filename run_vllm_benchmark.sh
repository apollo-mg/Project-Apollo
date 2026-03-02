#!/bin/bash

# Ensure we use the correct model path without moving models to another drive.
# We mount the local huggingface cache into the docker container so it can access
# the models natively.

MODEL="RedHatAI/DeepSeek-R1-Distill-Qwen-14B-FP8-dynamic"

echo "Starting vLLM benchmark using Docker with native ROCm 7.2 Triton and HIP graphs enabled..."

# We use the specialized ROCm 7.2 'Navi' development build, which contains the 
# optimizations specifically for consumer RDNA 4 (gfx1201) hardware.
IMAGE_NAME="rocm/vllm-dev:rocm7.2_navi_ubuntu24.04_py3.12_pytorch_2.9_vllm_0.14.0rc0"

# Note: VRAM is 16GB. The benchmark script uses gpu_memory_utilization=0.80 to leave
# room for HIP graph capture.

sudo docker run --rm \
    --name vllm-apollo \
    --network=host \
    --group-add=video \
    --ipc=host \
    --shm-size 16G \
    --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    --device /dev/kfd \
    --device /dev/dri \
    -e HSA_OVERRIDE_GFX_VERSION=12.0.1 \
    -e PYTORCH_TUNABLEOP_ENABLED=1 \
    -v "/media/mark/TG 2TB/huggingface_cache":/root/.cache/huggingface \
    -v $(pwd):/workspace \
    -w /workspace \
    $IMAGE_NAME \
    python3 vllm_benchmark.py --model $MODEL
