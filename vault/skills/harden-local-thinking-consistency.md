---
name: harden-local-thinking-consistency
description: Configure and tune the "Preserve Thinking" feature for local LLMs (Qwen, Darwin, Gemma) to ensure multi-turn decision consistency and prevent hallucination loops.
---

# Harden Local Thinking Consistency

Use this skill when local models show inconsistent multi-turn decision-making or when enabling `<think>` blocks causes `<tool_call>—:` hallucination loops (where the model cuts off its reasoning prematurely).

## 🚀 Procedure: Enabling "Preserve Thinking"

1.  **Server Launch Arguments**:
    - Add `--chat-template-kwargs '{"preserve_thinking":true}'` to your `llama-server` launch command.
    - This forces the server to include the model's internal thinking blocks in the conversation history passed back to the model.

2.  **Orchestrator Configuration (`profiles.json` or `profiles.yaml`)**:
    - Set `auto_disable_thinking_with_tools: false`.
    - **CRITICAL**: If this is set to `true`, the orchestrator will strip thinking blocks when a tool call is detected, often causing the model to lose context and enter an "apology loop" or hallucinate tool syntax.
    - Ensure `extra_body` is configured to pass `chat_template_kwargs` to the model provider:
      ```json
      "extra_body": {
        "chat_template_kwargs": {
          "preserve_thinking": true
        }
      }
      ```

3.  **Sub-agent Inheritance**:
    - Sub-agents (`codebase_investigator`, `delegate_task`, `software_engineer`) should inherit these settings. 
    - Verify that the dynamic config loader is pulling from the primary `architect` profile.

## ⚠️ Pitfalls & Verification

- **Hallucination Loop**: If you see the model outputting `<tool_call>—:` or empty strings followed by an apology, check if `auto_disable_thinking_with_tools` is `true`. Switch it to `false`.
- **Token Bloom**: Preserving thinking blocks significantly increases token consumption (often 2x-4x per turn). Ensure your context window is sized correctly (e.g., 64k for RX 9070 XT) and that context compaction logic is active.
- **Verification**: Tail the `llama-server` output. Look for the `restored context checkpoint` messages. If `preserve_thinking` is working, you will see the `<think>` blocks inside the prompt content sent to the model for the next turn.
