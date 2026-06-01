---
name: implement-agent-fidelity-logging-foundry
description: Implementation of "The Foundry"—a high-fidelity logging pipeline to capture structured agent traces (Turn -> Thought -> Action -> Result -> Answer) for future model fine-tuning and fine-grained auditing.
---

## When to Use
- When building an agentic system that requires future fine-tuning on project-specific data.
- To audit complex multi-step reasoning failures by inspecting the thinking trace and tool results.
- When transitioning from live agents to specialized, smaller models (distillation).

## Procedure
1. **Define Unified Log Schema**: Establish a JSONL structure for conversation turns.
    ```json
    {
      "timestamp": "ISO-8601",
      "source": "live_agent",
      "conversation": [
        {"role": "user", "content": "..."},
        {
          "role": "assistant",
          "thought": "... reasoning trace ...",
          "actions": [{"tool": "...", "args": {...}}],
          "tool_results": ["..."],
          "content": "Final answer"
        }
      ]
    }
    ```
2. **Implement Logger Class**: Create a `FoundryLogger` to manage the appending of structured turns to a central JSONL file.
3. **Integrate into Agent Loop**: Call the logger at the *end* of each successful session/turn, capturing the full history, thinking trace, and tool results.
4. **Ingest Existing Logs**: Implement ingestion methods for different session formats (e.g., Gemini CLI JSONs, legacy chat history) to backfill the Foundry dataset.
    - Loop through session files.
    - Extract user/assistant message pairs.
    - Map fields to the unified schema.
5. **Periodic Data Cleaning**: Use scripts to deduplicate entries or filter out turns that failed (e.g., those triggering circuit breakers).

## Pitfalls and Fixes
- **Data Explosion**: Logging every turn can fill disk space quickly. **Fix**: Implement retention policies or rotate the JSONL files.
- **Privacy Leakage**: Passwords or keys in tool results are logged. **Fix**: Apply redaction regex patterns in the `log_turn` method before writing.

## Verification
- Run a conversation with the agent.
- Check the `vault/foundry_logs.jsonl` (or configured path) and verify that the `thought` and `tool_results` fields are populated correctly.
- Ensure the output is valid JSONL (one JSON object per line).
