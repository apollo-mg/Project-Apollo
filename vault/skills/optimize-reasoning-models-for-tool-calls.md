---
name: optimize-reasoning-models-for-tool-calls
description: Procedural methods to disable "thinking" blocks specifically for tool calls in local LLMs (Qwen, Gemma) to increase TPS in agentic loops.
---

## When to Use
Use this skill when using a local reasoning model (e.g., Qwen 3.5, Gemma 4) for autonomous agent tasks where the "thinking" block is redundant for obvious tool selection. Disabling thinking for these turns significantly increases Tokens Per Second (TPS) and prevents hitting output token limits during the reasoning phase.

## Procedure

### 1. Jinja Template Overrides (Official Method)
If the inference engine (e.g., vLLM, LM Studio, or a custom Python script) supports template variable overrides, set the `enable_thinking` flag to false.
- **Example (Jinja):** `{%- set enable_thinking = false %}`
- **Usage:** Pass this via `chat_template_kwargs` or similar API parameters during the tool-calling turn.

### 2. Grammar-Guided Generation (Brute Force)
Use GBNF grammars (in `llama.cpp` or compatible backends) to mathematically prevent the model from starting a thought block.
- **Logic:** Force the model's first output character to be `{`.
- **Effect:** The model is unable to output the activation token for thinking (e.g., `<think>`) and is forced to skip directly to the JSON tool arguments.

### 3. Logit Bias (The Token-ID Method)
Manually ban the activation tokens for thinking.
- **Action:** Identify the Token ID for the opening thought tag (e.g., `<think>`, `<|thought|>`, or `<|channel>thought`).
- **Command:** Set the `logit_bias` for that ID to `-100` (impossible) in the API request.
- **Note:** Ensure the closing tag is also handled or the model may produce erratic output.

### 4. Prompt-Based Soft Switch
Some models (like Qwen 3) recognize specific markers to toggle thinking.
- **Disable:** Append `/no_think` to the end of the user prompt or system message.
- **Enable:** Use `/think` when deep reasoning is required before an action.

## Pitfalls and Fixes
-   **Symptom**: Model selects the wrong tool or hallucinates arguments.
    -   **Cause**: The task actually required reasoning to disambiguate tool choice.
    -   **Fix**: Re-enable thinking for complex or ambiguous tasks; only disable it for "reflexive" utility tasks.
-   **Symptom**: Model outputs raw `<think>` text instead of skipping it.
    -   **Cause**: The chat template was not correctly updated, or the model's internal prompt format was violated.
    -   **Fix**: Verify the exact activation token for the specific model version.

## Verification
-   **TPS Check**: Monitor the generation speed. Tool calls should start streaming almost instantly without the typical delay of a reasoning block.
-   **Token Limit Check**: Verify that the model no longer hits `max_tokens` limits due to an oversized internal monologue.
-   **Output Check**: Inspect the raw response; it should start with the tool call JSON (e.g., `{ "tool": ... }`) with no preceding tags.
