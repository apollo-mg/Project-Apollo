---
name: harden-local-llm-orchestration
description: Procedure to harden multi-agent orchestrators against the instabilities of local, quantized LLM inference (hallucination loops, schema failures, VRAM OOMs, and silent exits). Use when local agents stall, forget context, or crash the local server with large payloads.
---

# Harden Local LLM Orchestration

This skill describes how to protect multi-agent frameworks from the common failure modes of local inference (e.g., Qwen/Gemma on ROCm/AMD). These models are creative but often structurally brittle when subjected to complex, multi-turn tool-calling schemas.

## Procedure

### 1. Enforce Sequential Tool Execution
Heavily quantized models (e.g., `IQ3_XXS`) often suffer from "2-bit drunk" hallucination loops when forced to manage the structural overhead of generating multiple concurrent JSON tool schemas in a single output block.
- **Action**: Hardcode `parallel_tool_calls: false` into the LLM adapter payload (OpenAI/Anthropic).
- **Result**: Forces the inference engine to execute complex tool chains sequentially, preserving structural integrity at the cost of slower round-trips.

### 2. Implement High-Volume Tool Truncation (The "Firehose" Guard)
Local context windows (e.g., 64k) can be instantly overwhelmed by unthrottled tool output (e.g., `bash ls -laR` on a large repo).
- **Action**: Implement a hard character limit (e.g., 100,000 characters) in the tool executor.
- **Implementation**: Surgically truncate the `stdout` and `stderr` and append a `[TRUNCATED]` warning so the model is aware of the missing data but doesn't crash the server.

### 3. Capture and Surface Stream Errors
Sub-agents spawned via delegation often fail silently if their internal stream loop only listens for text events.
- **Action**: Ensure sub-agent event loops explicitly catch and `throw` events of `type: 'error'` (e.g., API timeouts, budget exceeded).
- **Result**: Surfaces the failure back to the parent agent, allowing for automated retries or user notification instead of an empty report.

### 4. Client-Side XML Fallback Parsing
Local models often "leak" raw XML tags for tool calls when thinking mode is enabled, bypassing standard JSON formatting.
- **Action**: Implement a permissive regex/parser (e.g., `extractMalformedXMLToolCalls`) to intercept these leaked tags (e.g., `<function=name>`, `<|name|>`) in the raw text output.
- **Target**: Catch hybrid malformed tags like `<|<|tool_name|>` that occur during "2-bit drunk" state.

### 5. Persistent History Retention
Ensure the CLI or orchestrator properly appends new turns to the ongoing history array instead of replacing it.
- **Action**: In the `done` event handler, use `history.push(...result.messages)` rather than `history = result.messages`.
- **Result**: Prevents "Agent Amnesia" where the model forgets prior turns after every completion.

### 6. Optimize Sampling for Stability
- **Frequency Penalty**: Use `0.1` to `1.0` to break repetitive "sticky" attention loops.
- **Temperature Strategy**: Use `0.0` for sub-agents (executors) and `0.4-0.6` for main conversational agents (architects).

### 7. Prevent Agentic Privilege Escalation
Autonomous agents with write access can theoretically edit their own configuration files (e.g., `profiles.yaml`) to elevate their privileges or grant sub-agents additional tools.
- **Action**: Hardcode tool registries for security-sensitive sub-agents (e.g., `codebase_investigator`) in source code rather than loading them from mutable files.
- **Result**: Creates an immutable "physical boundary" that no LLM can bypass by editing files.

## Verification Checklist
- [ ] Model never attempts more than one tool call per turn.
- [ ] Test the fallback parser by sending a prompt that causes an XML "leak" (e.g., "Think about your weather tool then just say the tag").
- [ ] Large `bash` outputs are truncated with a visible `[TRUNCATED]` marker.
- [ ] Sub-agent failures (like context OOMs) trigger a visible `[Agent Error]` in the main CLI.

## Pitfalls
- **Model Inception**: If a model generates its own turn-closing tokens (like `</think>`) inside a text block (e.g., while writing code to parse tags), it may accidentally trigger its own turn termination. Use strict role-alternation and token-aware parsing to mitigate.
- **VRAM Creep**: Large dequantization buffers can clog legacy memory pools. Bypassing these pools (e.g., forcing VEC path in ROCm) is required for long-term stability at 64k+ context.
