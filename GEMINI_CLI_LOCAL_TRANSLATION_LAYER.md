# Gemini CLI to Local LLM Translation Layer: Architectural Overview
**Project:** Apollo OS (Sovereign Entity Architecture)
**Hardware:** AMD Radeon RX 9070 XT (16GB VRAM, RDNA 4) / CachyOS
**Backend:** `llama-server` (Custom ROCm/TurboQuant fork)

## 1. The Core Challenge: Schema Mismatch
Gemini CLI is natively designed to interface with Google's proprietary Vertex AI / Gemini API ecosystem, which relies on highly specific, proprietary JSON schemas and XML injection tags for multi-turn tool orchestration. 
Conversely, the vast majority of local open-source models (Llama 3, Qwen, Mistral) are instruction-tuned on **OpenAI-compatible** function-calling formats. When forced to process Gemini CLI's foreign internal tool contracts (e.g., `web_fetch` requiring a single `prompt` string instead of a `url` parameter), local models experience "cognitive dissonance," leading to severe hallucinations, parameter omissions, and catastrophic conversational loops.

## 2. The Architectural Translation Layer
To successfully bridge Gemini CLI to an offline, local backend without altering the core Node.js application logic, we implemented a multi-layered translation strategy:

### A. Zero-Turn Hierarchical Context Injection (`GEMINI.md`)
Rather than wasting API turns on system instructions, we leveraged Gemini CLI's native capability to seamlessly inject context files. We established a strict hierarchy:
1.  **Global Context (`~/.gemini/GEMINI.md`):** Defines hardware constraints (16GB VRAM limit, no CPU offloading), OS preferences (CachyOS), and safety rules.
2.  **Project Context (`/mnt/TG_2TB/Projects/Apollo/GEMINI.md`):** Contains the "Sovereign Engineering Directives," specific ROCm workarounds (`MUL_MAT_ID` fixes, TurboQuant parameters), and architectural blueprints (Coordinator vs. Coder patterns).

This ensures the local model is pre-loaded with the necessary operational guardrails before it processes a single user token, effectively acting as an environmental translation layer.

### B. Hardware-Accelerated Guided Decoding (GBNF)
To combat the local models' tendency to output invalid JSON or hallucinate tool parameters when faced with foreign schemas, we utilized `llama.cpp`'s native **Grammar-Based Normal Form (GBNF)** engine. By passing strict JSON Schemas into the OpenAI-compatible `response_format` payload, the `llama-server` backend intercepts token probabilities at the hardware level, mathematically forcing the model to adhere to the required tool schema (The "Pydantic Shield" pattern).

### C. Extreme VRAM Compression (TurboQuant Asymmetric Caching)
Running an orchestration framework requires a massive, continuously rolling context window. To fit a capable "Lead Architect" model onto a 16GB GPU without spilling to system RAM (which destroys TPS), we deployed the `llama-cpp-turboquant` fork.
*   **The Config:** `-ctk turbo4 -ctv turbo3` combined with `HSA_ENABLE_SDMA=1` and `GGML_HIP_FORCE_MMQ=1`.
*   **The Result:** Successfully unlocked a stable 64,536-token context window, compressing the KV cache footprint drastically while maintaining high reasoning throughput.

## 3. Empirical Model Benchmarking (The Scientist's Model Lab)
Not all local models can survive the Gemini CLI environment. We established "The Model Lab" to empirically test models against the orchestrator's rigid demands.

### The Findings: Dense vs. Sparse (MoE) Architecture
*   **The System Coordinator (Qwopus 3.5 27B - Dense):** 
    *   *Quantization:* `IQ3_M`
    *   *Verdict:* **PASS.** The dense architecture proved incredibly resilient to quantization. It natively grasped foreign orchestrator schemas (even zero-shot adapting to Anthropic's Claude Code MCP tools) and successfully executed complex multi-step toolchains (read/write/verify) without breaking character or hallucinating parameters.
*   **The Daydream Daemon (Qwen 3.6 35B A3B - MoE):**
    *   *Quantization:* `IQ3_XXS`
    *   *Verdict:* **FAIL (For Orchestration) / PASS (For Offline Reasoning).** The heavily quantized sparse architecture shatters under the weight of strict, multi-turn JSON generation, falling into "2-Bit Drunk" apology loops when tool parameters are missing. However, its blazing fast native `<think>` blocks (~39 TPS) make it the superior model for offline, abstract logic tasks (The "Soul").

## 4. Next Steps: The Actionable Epiphany Pipeline
With the translation layer stabilized, the architecture moves from passive orchestration to proactive autonomy via the "Biological Memory Decay" tenet:
1.  **The Master Chronology:** All raw interaction logs are condensed into a single, high-signal narrative text file (`APOLLO_CHRONOLOGY.md`).
2.  **Daydream V2 (The Soul):** During idle cycles, the background Python daemon feeds chunks of the Chronology to the Qwen 3.6 MoE model, generating deep-thought epiphanies and architectural plans.
3.  **The Strict Filter (The System):** The generated epiphanies are immediately piped back through the API using strict Guided Decoding (JSON Schema). This mathematically filters out philosophical rambling, saving only concrete, executable plans to `actionable_epiphanies.jsonl` for the Qwopus Coordinator agent to implement automatically.