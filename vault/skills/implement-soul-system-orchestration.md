---
name: implement-soul-system-orchestration
description: Procedural separation of reasoning (Soul/Planner) and execution (System/Executor) models in multi-agent workflows to maximize reasoning depth while ensuring tool-calling reliability.
---

## When to Use
Use this skill when local high-reasoning models (e.g., Qwen 3.6 MoE, Gemma 4) suffer from "2-Bit Drunk" hallucination loops (generating empty JSON arguments or apologies) during tool-heavy turns. This pattern delegates complex planning to a "Soul" model and atomic execution to a stricter "System" model.

## Procedure

### 1. Select Role-Specific Models
- **The Soul (Planner)**: Choose a model with deep reasoning and native thinking blocks (e.g., Qwen 3.6 35B MoE, Gemma 4 26B MoE).
    - **Config**: `enable_thinking: true`, high temperature (0.6 - 1.0), large output token limit (4096+).
- **The System (Executor)**: Choose a dense, tool-reliable model (e.g., Qwopus 3.5 27B, Llama 3).
    - **Config**: `enable_thinking: false`, low temperature (0.0 - 0.2), GBNF grammars enabled (if supported by backend like `llama-server`).

### 2. Configure Agent Profiles
Define separate personas in your orchestrator (e.g., `profiles.json` for `open-multi-agent`).
```json
{
  "planner": {
    "role": "Epiphany Synthesizer",
    "model": "qwen-3.6-moe",
    "allowed_tools": ["file_read", "grep"],
    "temperature": 0.6
  },
  "executor": {
    "role": "Lead Architect",
    "model": "qwopus-27b",
    "allowed_tools": ["bash", "file_edit", "web_fetch"],
    "temperature": 0.1
  }
}
```

### 3. Orchestrate the Handoff (The Fork)
Use a "Coordinator -> Worker" pattern where the Planner (Soul) generates a structured task list and delegates them to the Executor (System).
- **Planner Instruction**: "Analyze the project structure and generate a Master Action Plan. Do NOT attempt to edit files yourself. Delegate individual file edits to the Lead Architect."
- **Executor Instruction**: "You are a surgical executor. Perform the following atomic task precisely as described. Verify your work after each step."

### 4. Implement Context Hygiene
When the Executor returns the result of a sub-task to the Planner:
- **Pruning**: Do NOT send the Executor's full reasoning trace back to the Planner.
- **Summarization**: Return only the tool output and a 1-sentence success confirmation to keep the Planner's context clean.

## Pitfalls and Fixes
- **Symptom**: Planner tries to call execution tools despite instructions.
  - **Cause**: The Planner's profile has too many "allowed_tools".
  - **Fix**: Strip execution tools (like `file_edit` or `bash`) from the Planner's registry; only allow `delegate_task`.
- **Symptom**: System model still fails JSON formatting.
  - **Cause**: Lack of syntax rigidity.
  - **Fix**: Use GBNF grammars to force the first output character to be `{` or use a "Pydantic Shield" to auto-correct schema errors.
- **Symptom**: VRAM OOM when running both models.
  - **Cause**: Hardware limits (e.g., 16GB VRAM) cannot hold two large models.
  - **Fix**: Use Zero-Cost Model Multiplexing (sharing the same server instance if both profiles use the same base model) or implement sequential sequential model swapping with a VRAM watchdog.

## Verification
- Execute a complex refactoring task: Verify the Planner correctly identifies all files needing changes and creates a sequential TaskQueue.
- Monitor the "System" turn: Verify it skips the `<think>` block entirely and immediately outputs the correct JSON tool call.
- Check the logs for successful handoffs between the two profile IDs.
