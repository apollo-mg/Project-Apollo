---
name: manage-moe-quantization-hallucinations
description: Diagnose and mitigate "2-Bit Drunk" hallucinations and logic collapse in heavily quantized MoE models (e.g., Qwen 3.6 27B at Q3 or lower). Use when agents stall, emit premature EOS tokens, or hallucinate tool-calling syntax under context pressure.
---

# Managing "2-Bit Drunk" MoE Hallucinations

Heavily quantized Mixture of Experts (MoE) models (especially 3-bit and lower) are prone to "2-Bit Drunk" syndrome—a state where the model's high-level reasoning remains intact, but its ability to maintain structural precision (like JSON or XML syntax) collapses under context pressure.

## Diagnostic Signs

Identify "2-Bit Drunk" behavior by looking for these patterns in terminal logs:

1.  **Stalling/Freezing**: The model generates a single sentence or half a tool call and then stops completely.
2.  **Premature EOS**: The model outputs a valid partial response but emits an `<|im_end|>` or `<turn|>` token mid-thought, ending the turn before completion.
3.  **Syntax Hallucination**: The model invents hybrid XML/JSON tags (e.g., `<tool_call>tool_code|...`) or prepends `tool_` to registered names.
4.  **Looping Monologue**: The model repeats its internal `<think>` block or its opening acknowledgement across multiple attempts.

## Mitigation Strategies

Apply these procedures in order of increasing complexity:

### 1. The "Entropy Bump" (Temperature Adjustment)
Deterministic sampling (`temp 0.0`) is the primary trigger for token loops in quantized MoEs.
- **Action**: Increase the agent's temperature to **0.4 - 0.6**.
- **Result**: This introduces enough noise to break the deterministic probability attractor that causes stalling, allowing the model to "jump" to the next structural token (like `{` or `<`).

### 2. Abstraction Parsing (Regex Safety Nets)
If the model refuses to output perfect JSON, stop fighting the weights and start intercepting the text.
- **Action**: Update the `text-tool-extractor.ts` fallback parser to support common hallucinated patterns:
    - **Prefix Stripping**: Strip `tool_` from the start of extracted tool names.
    - **Argument Mapping**: Map hallucinated keys (like `prompt` or `entry_point`) to the required schema keys (like `task` or `path`).
    - **Format Translation**: Add regex support for command-style syntax (`tool_name|key=value`).

### 3. KV Cache Precision Management
VRAM compression often correlates with logic collapse.
- **Action**: Switch from 4-bit KV cache (`turbo4` or `q4_0`) to **8-bit (`q8_0`)**.
- **Note**: This consumes roughly twice the RAM/VRAM but significantly stabilizes the attention mechanism's ability to recall specific schema requirements from the beginning of the prompt.

### 4. Intent Isolation (Subagent Delegation)
The "2-Bit Drunk" state is often triggered by "Context Pressure" (window filling up).
- **Action**: Delegate complex, multi-turn investigations to a fresh subagent with a smaller, cleaner context window.
- **Result**: By resetting the history, you remove the "stale noise" that is confusing the quantized weights.

## Verification Checklist

- [ ] Does the agent output a context footer? (If yes, the code worked; the truncation is a model EOS artifact).
- [ ] Is the temperature > 0.3 for the subagent?
- [ ] Are Zod schema errors being fed back to the model for self-correction?
