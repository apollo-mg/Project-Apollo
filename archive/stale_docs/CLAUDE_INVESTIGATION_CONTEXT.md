# Claude Code Leak Investigation Directives
# Target: Anthropic "Claude Code" Source Map Leak (March 31, 2026) / "open-multi-agent" repo

## 🎯 Goal
Investigate the leaked Anthropic `claude-code` TypeScript architecture and its open-source derivatives (e.g., `open-multi-agent`). Extract the architectural blueprints, orchestration patterns, and prompt schemas so we can recreate the "Sovereign Equivalent" on a local AI lab.

## ⚙️ Target Hardware Context
Any solutions extracted must be mapped to this local hardware topology:
*   **GPU (The VRAM Hot Zone):** AMD Radeon RX 9070 XT (16GB VRAM). Hosts the primary "Coordinator/Architect" model (Qwen 3.5 35B at IQ2_XXS, taking ~11GB).
*   **CPU (The L3 Cache / Warm Zone):** Ryzen 7 5700X3D (96MB L3 Cache) with 32GB DDR4. Hosts the `MessageBus`, memory databases, and smaller background agents (e.g., CoPaw-9B) running purely on CPU/RAM.

## 🔍 Specific Extraction Targets

### 1. The "Coordinator" Pattern & TaskQueue
*   How exactly does Claude Code break down a massive user prompt into a `TaskQueue`?
*   We need the specific system prompts or XML schemas Anthropic uses to force the LLM to output a structured dependency graph rather than just answering the prompt.

### 2. The `MessageBus` (SharedMemory)
*   How do the sub-agents communicate without passing the entire 100k+ token conversation history back and forth?
*   Analyze the `MessageBus` implementation in `open-multi-agent`. How is state saved, and how do worker agents pull tasks off the bus?

### 3. Zod Schema Validation & "2-Bit Drunk" Mitigation
*   Local quantized models (like our 2-bit 35B) often hallucinate markdown or fail strict JSON formatting.
*   How does the leaked architecture use Zod (or similar validation) in its `defineTool()` function to actively intercept and auto-correct formatting errors before they break the loop?

### 4. The KAIROS Daemon (Background Autonomy)
*   Look for references to the unreleased `KAIROS` feature or "Background Agents."
*   How does Anthropic handle "dream memory consolidation" or persistent background loops? We are building a "Daydream Daemon," and we need to see how their loop is structured.

## 📝 Deliverables
Do not rewrite the entire TypeScript codebase. Instead, provide:
1.  **Architecture Diagrams (Mermaid/Text):** Show the flow of a prompt from Coordinator -> MessageBus -> Worker Agent.
2.  **Prompt Templates:** The raw system instructions Anthropic uses for tool calling and task delegation.
3.  **Python Translation Blueprints:** Conceptual guides on how to rewrite the Node/TypeScript `MessageBus` logic into a lightweight Python supervisor that talks to a local `llama.cpp` server (port 8082).

## ⚠️ Operational Guardrails
*   **Do not** execute or run any of the proprietary leaked Anthropic code directly.
*   Analyze the structural concepts and the clean-room reimplementations (like `open-multi-agent`).
*   Prioritize local latency and low VRAM footprint. If a leaked technique requires 100k context windows for every sub-task, discard it and find the efficient edge alternative.