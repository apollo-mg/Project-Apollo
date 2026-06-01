---
name: multiplex-local-llm-agents
description: Share a single LLM server instance across multiple specialized agents to eliminate VRAM swapping latency.
---

## When to Use
Use this skill when designing multi-agent workflows (e.g., Coordinator -> Coder) on hardware with limited VRAM (like the 16GB RX 9070 XT). This avoids "VRAM Thrashing" by using a single resident model instance to power multiple agent personas.

## Procedure

### 1. Model Selection (The Symbiosis)
Identify the bottleneck of the current task phase:
- **Phase 1: Synthesis/Planning** -> Use a **Sparse MoE** (e.g., Gemma 4 26B) with a large context window (`-c 65536`) to ingest high-volume logs/spools.
- **Phase 2: Execution/Coding** -> Use a **Dense Model** (e.g., Qwen 27B) with a tight context window (`-c 8192`) for maximum reasoning fidelity.

### 2. Implementation (The Single-Adapter Pattern)
Configure your multi-agent script (TypeScript/Python) to share a single LLM adapter:
```typescript
// Shared adapter pointing to the local server
const sharedAdapter = createAdapter({
  baseUrl: "http://127.0.0.1:8082/v1",
  apiKey: "sk-1234"
});

// Instantiate specialized agents using the SAME adapter
const coordinator = new AgentRunner({
  adapter: sharedAdapter,
  systemPrompt: COORDINATOR_SYSTEM_PROMPT, // Instructions for planning
});

const coder = new AgentRunner({
  adapter: sharedAdapter,
  systemPrompt: CODER_SYSTEM_PROMPT, // Instructions for tool use/coding
});
```

### 3. Orchestration Loop
Use a control loop to pass context between the personas without reloading models:
1. **Coordinator** identifies the next task from the plan and outputs a JSON delegation directive.
2. **Control Loop** catches the directive and invokes the **Coder**.
3. **Coder** executes tools and reports success/failure.
4. **Control Loop** feeds the report back to the **Coordinator** to update the plan.

## Pitfalls and Fixes
- **Symptom:** High latency (~15s) between agent turns.
  - **Cause:** Each agent is reloading a different model or context into VRAM.
  - **Fix:** Ensure all agents in the current phase are pointing to the same port/PID and that the context window (`-c`) fits the resident model.
- **Symptom:** Agent "forgets" the plan or tool rules.
  - **Cause:** In a shared model instance, the model relies entirely on the system prompt to distinguish its role.
  - **Fix:** "Lobotomize" agents by stripping unnecessary tools from their `ToolRegistry`. For example, the Coordinator should only have `file_read`/`file_write` for plan management, while the Coder has the full toolset.

## Verification
- Monitor `llama-server` logs; you should see requests for different agents arriving at the same server instance.
- Check GPU power draw (`rocm-smi`); it should remain stable during agent transitions, indicating no model reload.
