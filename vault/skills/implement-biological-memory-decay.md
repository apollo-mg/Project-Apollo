---
name: implement-biological-memory-decay
description: Procedure to implement non-destructive chat compaction strategies (Biological Memory Decay) to manage long-term conversation context for local LLMs.
---

# Implement Biological Memory Decay (Chat Compaction)

This skill describes how to implement a tiered strategy for managing context window pressure in long-running agentic conversations. This prevents "context window death spirals" where the model loses its ability to follow instructions as the history grows.

## Procedure

1. **Enable Lightweight Tool Result Compression**:
   Implement a rule-based compressor that runs between every turn.
   - **Mechanism**: Once the LLM has responded to a large `tool_result` block (e.g., > 10,000 chars), replace the raw content in history with a metadata marker: `[Tool result: <name> — <size> chars, compacted]`.
   - **Benefit**: Instantly recovers VRAM without LLM overhead or loss of core decisions.

2. **Configure Rule-Based Context Compaction**:
   Set a token threshold (e.g., 50,000 tokens) to trigger structural thinning.
   - **Mechanism**: Identify a "recent window" (e.g., the last 4 turns) to keep intact. For turns older than this window, truncate long assistant text blocks (including `<think>` blocks) into 200-character excerpts.
   - **Safety**: **Never** delete `tool_use` blocks, as they represent the agent's historical decision-making logic.

3. **Implement LLM-Driven Summarization**:
   Use a background LLM pipeline to condense old history when context limits are nearly reached.
   - **Mechanism**: Trigger when tokens exceed a specific limit (e.g., 55,000). Send the oldest part of the history to a low-temperature (T=0.1) model with the prompt: *"Summarize the core technical findings and decisions in this segment of the conversation."*
   - **Persistence**: Cache the summary and inject it back into the history array as a new system/user message, then purge the summarized turns.

4. **Wired into Profiles**:
   Store these settings in the agent's profile (e.g., `profiles.json`) so they can be toggled per-role:
   ```json
   {
     "architect": {
       "compress_tool_results": true,
       "context_strategy": {
         "type": "summarize",
         "maxTokens": 50000
       }
     }
   }
   ```

## Verification Checklist

- [ ] Verify that `tool_result` compression fires immediately after a turn and is reflected in the next prompt.
- [ ] Confirm that error results in tool calls are **excluded** from compression to ensure the model can still debug.
- [ ] Test the summarization trigger by artificially lowering the `maxTokens` limit and verifying the background summary call.

## Pitfalls

- **Context Fragmentation**: Over-aggressive summarization can cause the model to forget specific variable names or file paths. Always ensure the summarizer is instructed to preserve "technical entities."
- **Sequential Interference**: Ensure the background summarization pause is handled gracefully in the CLI UI (e.g., print a `[Compacting Context...]` message).
