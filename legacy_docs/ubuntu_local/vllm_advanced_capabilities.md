# vLLM Advanced Capabilities & ROCm 7.2 Optimizations (2026)

This document serves as the local reference for advanced vLLM features available on the AMD Radeon RX 9070 XT via ROCm 7.2, specifically tailored for the Sovereign AI OS (Project Apollo).

## Core Philosophy: The "One-Shot Workhorse"
Unlike Ollama's dynamic memory swapping (ideal for the multi-model Apollo swarm), vLLM statically pre-allocates VRAM to maximize enterprise-level throughput. 
**Primary Use Case:** High-speed batch processing (e.g., Librarian document ingestion, massive email extraction, or parallel vision analysis) where the container is spun up, completes the massive task, and is shut down to free VRAM.

## 1. Automatic Prefix Caching (RAG Acceleration)
When analyzing massive documents (WORM drive data) across multiple queries, vLLM caches the prompt hash.
*   **Flag:** `--enable-prefix-caching`
*   **Effect:** Drops "Time-to-First-Token" (TTFT) from seconds to milliseconds when reusing the same context (like a WORM drive W3 data dump) across consecutive API calls.

## 2. Speculative Decoding
Combines a large "Target" model (e.g., 14B) with a tiny "Draft" model (e.g., 1B).
*   **How it Works:** The Draft model rapidly predicts the next several tokens, and the Target model verifies them in parallel.
*   **Effect:** Delivers the reasoning quality of the 14B model but at 2x-3x the generation speed.
*   **Usage:** Requires VRAM space for both models, but is the ultimate text-generation speed hack when VRAM permits.

## 3. Guided Decoding (Strict Schema Enforcement)
Native integration with `outlines` to mathematically force the LLM to output valid data structures.
*   **Usage:** Pass a Pydantic schema or Regex to the `/v1/chat/completions` API endpoint.
*   **Effect:** Zero parsing errors. It is physically impossible for the model to hallucinate conversational text when asked for strict JSON/CSV.

## 4. Continuous Batching (`run-batch`)
For massive offline data processing (e.g., 50,000 W3 rows).
*   **Usage:** `vllm run-batch prompts.jsonl results.jsonl`
*   **Effect:** Bypasses API/HTTP overhead entirely. Uses highly optimized scheduling to chew through massive datasets overnight.

## 5. Vision-Language Model (VLM) Native ROCm Support
As of early 2026, vLLM has First-Class ROCm support for **Qwen2.5-VL** and **Qwen3-VL**.
*   **Agentic Capabilities:** Qwen3-VL is optimized for GUI navigation and spatial reasoning.
*   **Key Flag for 16GB GPUs:** `--mm-encoder-tp-mode data` decouples the vision encoder from the LLM, preventing memory bottlenecks during high-resolution multi-frame inference.
*   **Use Cases:** Massive PDF flyer batch processing (Procurement Mind) or multi-frame WORM drive W3 data extraction without memory swapping.

## Golden Rules for RX 9070 XT (16GB VRAM)
1. **14B Dense:** Must be AWQ/GPTQ 4-bit (Leaves ~9GB for KV Cache). FP8 will OOM during graph capture.
2. **30B+ / MoE:** Too large for static VRAM allocation. Use Ollama with RAM spillover instead.
3. **vLLM Startup:** Set `PYTORCH_TUNABLEOP_ENABLED=0` to skip 40-minute Triton/HIP graph warmups if you just need a quick test. Set to `1` for maximum production speed.