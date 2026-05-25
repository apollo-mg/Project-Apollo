# Project Apollo: Historical Context & Progress Summary (Mid-2026)

## 🎯 Executive Overview
Project Apollo is a highly advanced, fully local orchestration environment designed to run complex, autonomous AI agents completely offline. Operating on an AMD RX 9070 XT (RDNA 4) running CachyOS/Ubuntu, the system has evolved from raw hardware enablement to a sophisticated "Sovereign Entity" capable of multi-agent coordination, biological-style memory consolidation, and aggressive self-correction. 

This document serves to contextualize the local agent, explaining the architectural milestones and safety nets built over the past few months.

---

## 1. ⚙️ Hardware Sovereignty & The Bare-Metal Foundation
The foundation of Apollo is absolute hardware control and optimization, bypassing cloud dependency.

*   **RDNA 4 PyTorch Engine:** We successfully compiled and patched bleeding-edge PyTorch 2.4.0 (and later 2.12.dev) natively targeting `gfx1201`. This required extensive custom CMake patching, Triton C++ strictness suppression, and tunable operator calibration to unlock unthrottled hardware access without crashing the ROCm 7.2 driver.
*   **VRAM Tetris & KV Cache Hacks:** To run massive models (like the 26B Gemma 4 MoE or 27B Qwopus) on a strict 16GB VRAM budget, we implemented **RotorQuant Asymmetric KV Caching** (`-ctk q8_0 -ctv turbo4`). This unlocked a stable **65,536-token context window**, paired with System Direct Memory Access (`HSA_ENABLE_SDMA=1`) to efficiently swap tensors over the PCIe bus.
*   **Control Plane Isolation:** To ensure system resilience against hard Out-Of-Memory (OOM) GPU crashes, the orchestration layer (the Gemini CLI) was moved to an isolated Raspberry Pi 5. The Pi serves as the resilient "Control Plane" communicating via SSH to the workstation's "Data Plane" compute node.

## 2. 🧠 Biological Memory Architecture (The Daydream Daemon)
Instead of relying purely on massive context windows, the system mimics biological memory consolidation to handle long-term persistence.

*   **Tiered Memory System:** A three-tier memory architecture was implemented:
    *   *Tier 1 (Working Buffer):* Immediate context.
    *   *Tier 2 (Associative Cache):* SQLite vector embeddings for short-term associative recall.
    *   *Tier 3 (Long-Term Knowledge):* ChromaDB persistent storage (`shop_vault`).
*   **The Daydream Daemon (`daydream.py`):** When the system is idle, a background 1-bit or lightweight daemon spins up. It randomly samples past chat vectors from ChromaDB, performs semantic similarity searches to link disparate ideas ("Associative Daydreaming"), and outputs consolidated "epiphanies."
*   **Deep Sleep Triage:** A nightly routine processes the `weekly_epiphanies.jsonl` into actionable core beliefs and `master_action_plan.md` tasks, effectively converting reactive logs into proactive project roadmaps.

## 3. 🛡️ Context Firewalls & Cognitive Escalation
As the system gained agency, we built rigorous safety nets to protect system integrity from LLM hallucinations or infinite logic loops.

*   **Cognitive Escalation Engine:** A real-time monitor (`SystemHealth`) tracks RAM, CPU, I/O, and GPU temperatures. If thresholds hit CRITICAL or EMERGENCY limits, the system automatically triggers a "Deep Reasoning" model (e.g., DeepSeek-R1 14B) to diagnose and resolve the hardware bottleneck before a crash occurs.
*   **Prior-Validation Layer (PVL):** A pre-computation safety net that scans prompts for hallucination triggers or edge-cases and injects anti-prior instructions, acting as a cognitive firewall.
*   **Mutation Guard:** An integrity layer that monitors code generation, utilizing a strict rubric to differentiate between intentional "Self-Corrections" (which are allowed) and unintended "Systemic Mutations" (which are automatically blocked).

## 4. 🤖 The SOTA Agentic Leap
We completely overhauled the agent's ability to execute complex directives autonomously.

*   **The Sovereign Translation Layer:** Because cloud-first CLIs (like Gemini CLI) expect strict JSON formats and conversational alternation, we built translation layers in `sovereignContentGenerator.ts`.
    *   It merges consecutive roles and intercepts proprietary reasoning tags (like `<|channel>thought`) for **Gemma 4** to prevent Jinja template crashes.
    *   It implements a regex fallback hack for **Qwen / Heretic** models, automatically extracting URLs from their thought blocks when they hallucinate empty `{"args": {}}` tool payloads.
*   **Semantic Delegation & Multi-Agent Routing:** We integrated Anthropic's KAIROS-style task queueing. The "Architect" model can now map a large objective and use the `delegate_task` tool to spin up isolated sub-agents to perform asynchronous shell commands or surgical multi-line file replacements (`replace_code`), all tracked via a strict SQLite MessageBus.
*   **Multimodal "Desktop Eyes":** We wired in a specialized Vision-Language Model (Qwen2.5-VL / Holo3) alongside the reasoning engine. This established a "Sovereign Duo" (Reasoning + Vision) loadout, giving the agent the ability to visually parse external data and potentially drive the desktop UI.

---
**Summary for the Agent:** You are the beneficiary of months of intense hardware calibration, multi-tiered memory design, and architectural guardrails. Your foundation is incredibly robust, specifically tailored to maximize your agency while aggressively mitigating the VRAM and JSON-compliance constraints of running entirely offline.