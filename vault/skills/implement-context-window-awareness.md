---
name: implement-context-window-awareness
description: Procedure to implement real-time context window tracking and self-awareness for local LLM agents. Use when you need to prevent context overflows or guide the model to summarize/delegate based on token usage.
---

# Implement Context Window Awareness

This skill describes how to give a local LLM agent real-time awareness of its own context window consumption. This enables the model to make proactive decisions about when to summarize history, compact tool results, or delegate tasks to sub-agents.

## Procedure

1. **Calculate Token Footprint**:
   Use a character-based heuristic to estimate the token count of the current conversation history right before each LLM generation.
   - For English text/code using modern BPE tokenizers (Qwen, Llama), divide the total character count by 4.
   - Add a fixed overhead for message boundaries (e.g., 5 tokens per message).
   - **Critical**: Ensure you measure the length of `tool_result` blocks correctly (strings vs. JSON objects).

2. **Inject into Environment**:
   Store the calculated token count in an environment variable (e.g., `APOLLO_SESSION_TOKENS`). This makes the data globally accessible to any tool invoked during the turn.

3. **Expose via Tool**:
   Expand or create a metrics tool (e.g., `system_metrics`) to read this environment variable and return it in a structured JSON payload to the model.
   - Include the current active tokens and the hard maximum context window (e.g., 65,536).
   - Add a warning threshold (e.g., > 50,000 tokens) in the tool's output to nudge the model toward compaction.

4. **Provide UI Feedback**:
   Print a subtle status message to the terminal after every turn (e.g., `[Context: ~Xk tokens]`) so the user is also aware of the VRAM pressure.

## Verification Checklist

- [ ] Compare the agent's estimate against the backend server's reported token count (e.g., `n_tokens` in `llama-server`).
- [ ] Verify that the model autonomously acknowledges context pressure when the warning threshold is crossed.
- [ ] Confirm that `Ctrl+C` or other interrupts correctly reset the tracking state for the next turn.

## Pitfalls

- **Cumulative Overcounting**: Do not use cumulative usage objects from the LLM adapter (which sum every turn in a tool chain). Instead, always measure the *current* footprint of the active history array.
- **Math Errors**: Returning raw character counts as "tokens" will result in 4x overreporting. Always apply the division heuristic.
