# ACTIVE PROJECT: Jarvis Integration (formerly Shop Buddy)
**Status:** Phase 6.5 - Infrastructure Path (vLLM PoC)
**Current Goal:** Breaking the VRAM bottleneck using vLLM Prefix Caching and PagedAttention.

## Current Tasks:
1. [x] Hardened System 2 Synthesis (Safety Audit).
2. [x] Resident Receptionist (Llama 3.2 1B) for latency reduction.
3. [ ] Execute `prefix_cache_benchmark.py` against vLLM container.
4. [ ] Analyze TTFT reduction (Target: >70%).
5. [ ] Research migration from Ollama to resident vLLM OpenAI-compatible API.

## Recent Findings:
*   **Infrastructure Shift:** Transitioning from sequential model swapping to a resident vLLM backend.
*   **VRAM Stability:** Need to monitor `rocm-smi` during PagedAttention allocation.
*   **Docker PoC Command:** 
    ```bash
    docker run -it --network=host --group-add=video --ipc=host --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined --device=/dev/kfd --device=/dev/dri \
    -e HSA_OVERRIDE_GFX_VERSION=11.0.0 -e VLLM_ROCM_USE_AITER=0 \
    -v ~/.cache/huggingface:/root/.cache/huggingface rocm/vllm-dev:nightly \
    python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct \
    --enable-prefix-caching --gpu-memory-utilization 0.85 --max-model-len 8192 --dtype float16
    ```
