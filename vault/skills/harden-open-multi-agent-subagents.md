---
name: harden-open-multi-agent-subagents
description: Procedures to harden local sub-agents (codebase_investigator, software_engineer) against output leakage and fragmentation. Use when sub-agents return internal monologues or thought traces instead of final reports.
---

# Harden Open Multi Agent Subagents

## Overview

Local LLMs, especially Mixture-of-Experts (MoE) or heavily distilled "thinking" models (Qwen 3.6, Darwin-36B), often intermingle their internal reasoning traces (<think> blocks) with their final output. When used as sub-agents in the `open-multi-agent` framework, naive message extraction logic can accidentally concatenate all previous thought turns, burying the actual answer.

## Extraction Logic Hardening

The primary failure mode is sub-agents returning a "Frankenstein" report composed of every `<think>` block from a multi-turn tool loop.

### 1. Avoid Flat-Mapping All Assistant Messages
Do NOT use logic that flat-maps all text blocks from the history array. This captures the model's internal monologue turns.

**Vulnerable Pattern:**
```typescript
const allText = result.messages
  .filter(m => m.role === 'assistant')
  .flatMap(m => m.content.filter(b => b.type === 'text').map(b => (b as any).text))
  .join('\n\n')
```

### 2. Use Native `result.output`
Use the framework's native `result.output` (available via `runner.run()`). This explicitly filters for the **last** assistant message in the sequence, ensuring only the final synthesized report is returned to the parent agent.

**Hardened Pattern:**
```typescript
// Execute the sub-agent via run() to capture the final synthesized result
const result = await runner.run(history)
const finalSummary = result.output.trim() || 'Task completed but no final text was provided.'

return {
  data: `Engineering Report:\n\n${finalSummary}`,
  isError: false
}
```

## Prompt Engineering for Structural Integrity

### 1. Thinking Mode Constraints
If `enable_thinking` or `preserve_thinking` is active in `profiles.yaml`, the model will output thought traces. Ensure the sub-agent's system prompt instructs it to synthesize its final answer only AFTER completing its tool chain.

### 2. Mandatory Grounding
Force sub-agents to use a `file_read` or `grep` call BEFORE proposing an edit to ensure they are grounded in the actual file content, preventing hallucinations from old KV cache states.

## Model Selection for Orchestration

- **Fidelity > Parameter Count:** For sub-agents that must follow rigid JSON schemas, prefer higher quantization (Q5 or Q6) dense models over larger, heavily quantized MoE models. High-fidelity weights prevent "2-Bit Drunk" hallucination loops where the model apologizes endlessly or emits empty payloads.
- **Sampling Variance:** For distilled MoE "thinking" models, avoid `temperature: 0.0`. Use `0.4` to `0.6` to prevent the model from collapsing its reasoning blocks and returning empty strings.