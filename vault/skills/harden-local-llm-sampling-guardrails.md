---
name: harden-local-llm-sampling-guardrails
description: Stabilize local LLM agentic loops by configuring sampling parameters and disabling parallel tool execution. Use when local models (Qwen, Qwopus) repeat text, hallucinate tool arguments, or enter infinite apology loops.
---

# Harden Local LLM Sampling Guardrails

## Overview

Local LLMs (especially quantized MoE models) are significantly more fragile than frontier cloud models. They are prone to "sampling collapse" where they get stuck in repetition loops or "2-bit drunk" hallucinations during complex tool-calling tasks.

## 1. Stable Sampling Configuration

Apply these parameters to the model config (e.g., `AgentConfig` or `profiles.yaml`) to break loops and ensure logic survival:

| Parameter | Recommended | Reason |
|-----------|-------------|--------|
| `temperature` | `0.6` | High enough to avoid greedy loops; low enough to maintain logic. |
| `frequency_penalty` | `1.0` - `1.2` | **Critical.** Penalizes exact token repetition (e.g., "I apologize..."). |
| `presence_penalty` | `0.0` - `0.5` | Prevents the model from getting stuck on a single topic. |
| `top_k` | `20` - `40` | Limits the token pool to high-probability candidates. |
| `min_p` | `0.05` | Prunes the long tail of low-probability "noise" tokens better than Top-P. |

## 2. Force Sequential Tool Execution

Highly quantized models often fail when asked to generate multiple tool calls in a single turn (`parallel_tool_calls`). They may mix arguments, hallucinate merged tool names, or fail to close JSON blocks.

### The Guardrail
In the OpenAI adapter (`openai.ts`), hardcode `parallel_tool_calls: false` for all requests to local backends.

```typescript
const completion = await this.#client.chat.completions.create({
  model: options.model,
  // ...
  parallel_tool_calls: false, // Ensure sequential execution
  // ...
});
```

## 3. Native Reasoning Capture

Local servers like `llama-server` natively separate reasoning (e.g., `<think>` blocks) from the main content.

### The Procedure
Do NOT use regex to parse thinking out of the message text. Instead, read the `reasoning_content` field from the OpenAI-compatible response and wrap it yourself:

```typescript
const message = response.choices[0].message;
let fullText = '';

if (message.reasoning_content) {
  fullText += `<think>\n${message.reasoning_content}\n</think>\n`;
}
fullText += message.content || '';
```

## 4. Troubleshooting Repetition
If an agent is stuck in a loop despite these settings:
1. **Summarize History:** Use a `summarize` context strategy to clear the KV cache of the repeating tokens.
2. **Loop Detection:** Set `maxRepetitions: 3` in the agent config to trigger a warning injection ("WARNING: You appear stuck in a loop...").