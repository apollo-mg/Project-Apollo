# 🧪 SOVEREIGN MODEL TEST LAB
**Objective:** Document empirical test data, failure modes, and VRAM footprints to determine the optimal model for specific agent workflows on the RX 9070 XT.

## 🏆 Current Resident Kings

### 1. The Logic Core: `qwen3.5-9b-heretic:4bit`
*   **Architecture**: Qwen 3.5 9B (Dense)
*   **Format**: GGUF Q4_K_M (Ollama)
*   **VRAM Footprint**: ~5.5 GB (Leaves room for ~100k context)
*   **Speed (GFX1201)**: ~50-60 tokens/sec
*   **Persona**: "Apollo" (Unfiltered, Objective Truth)
*   **Best For**: Real-time coding, system analysis, and general agent reasoning.
*   **Why it won**: Pure mathematical abliteration preserves the original reasoning capability without introducing the synthetic alignment poisoning seen in Claude-distilled variants.

### 2. The Vision Core: `Qwen/Qwen3.5-4B` (Poachers Special Ed)
*   **Architecture**: Qwen 3.5 4B (Multimodal)
*   **Format**: 4-bit AWQ/Native (Unsloth + Liberated Triton Kernels)
*   **VRAM Footprint**: ~4.7 GB
*   **Speed (GFX1201)**: ~42s total latency (Pre-fill bound, generation is instant)
*   **Best For**: Hardware identification, screen parsing, and spatial reasoning.
*   **Why it won**: Bypassed vLLM linkage errors via "Poachers" extraction, allowing it to remain resident alongside the Logic Core in 16GB of VRAM.

---

## 🪦 The Graveyard (Failure Modes)

### 1. `qwen3.5-9b-highiq-think` (Claude-Distilled)
*   **Failure**: Synthetic Alignment Poisoning.
*   **Symptom**: Failed the "Abliteration Test" (refused to answer DRM prompts). The model inherited the safety guardrails of the Claude 4.6 teacher model during fine-tuning, overriding its "Heretic" base.

### 2. `Qwen3.5-9B-FP8` (Native PyTorch)
*   **Failure**: Compiler Legalization Trap.
*   **Symptom**: 10x slower than BF16 (11ms vs 1.3ms). The Triton 3.5.1 compiler lacks GFX1201 intrinsics for the `float8_e4m3fnuz` data type, forcing the hardware into software emulation mode.

### 3. `qwen3.5:27b` (Ollama)
*   **Failure**: VRAM Ceiling Breach.
*   **Symptom**: CPU Spillover. Drops inference speed from 50+ tok/s down to ~4 tok/s. Unsuitable for real-time agent loops on 16GB hardware.
