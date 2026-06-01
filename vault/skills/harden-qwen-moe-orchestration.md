---
name: harden-qwen-moe-orchestration
description: Harden Qwen 3.6 MoE models (Darwin, Qwopus) against hallucination loops and XML breakage during multi-turn tool orchestration. Use when a local MoE model emits shattered XML fragments, repeats tool calls, or enters a `<tool_call>—:` hallucination loop.
---

# Harden Qwen 3.6 MoE Orchestration

Qwen 3.6 Mixture-of-Experts (MoE) models (e.g., Darwin-36B, Qwopus-27B) have a strong training bias to initiate every response with an active reasoning (`<think>`) block. Standard "context-saving" template features that try to skip these blocks often trigger catastrophic failure modes.

## Failure Shield: Hallucination Loops

If you encounter the `<tool_call>—:` hallucination loop or "Shattered XML" errors:

1.  **Check `auto_disable_thinking_with_tools`**: This MUST be set to `false` in your `--chat-template-kwargs`.
    *   **Reason**: Setting it to `true` injects an empty `<think>\n</think>` block. MoE models "refuse" this empty block, start a new one anyway, and then hallucinate tool syntax across the broken block boundaries.
2.  **Verify `preserve_thinking`**: Set to `true`.
    *   **Reason**: While this increases context bloat, it ensures the model maintains strategic coherence across multiple turns. Darwin handles preserved thoughts safely without attention ruts.
3.  **Implement `max_tool_response_chars`**: Use a hard limit (e.g., `100000`) to prevent massive tool outputs from pushing the reasoning blocks out of the active context window.

## Procedural Launch (P100 / ROCm)

For maximum stability on hardware like dual Tesla P100s:

1.  **Engine Selection**: Use `buun-llama-cpp` for sm_60 CUDA support or the latest `llama-cpp-turboquant` for RDNA 4.
2.  **Launch Arguments**:
    ```bash
    llama-server -m your-moe-model.gguf \
        --jinja \
        --chat-template-kwargs '{"auto_disable_thinking_with_tools": false, "preserve_thinking": true, "max_tool_response_chars": 100000}' \
        -ctk q8_0 -ctv turbo4 \
        --kv-unified \
        --cache-idle-slots \
        --reasoning auto
    ```
3.  **Environment Variable**: Set `export TURBO_AUTO_ASYMMETRIC=0` if you encounter "Illegal Memory Access" errors.

## Verification Checklist

- [ ] Model starts every turn with a non-empty `<think>` block.
- [ ] Tool results are truncated before they hit the context limit.
- [ ] No occurrences of `<tool_call>—:` in the logs.
- [ ] Strategic intent (the "Soul") is maintained across 5+ tool turns.