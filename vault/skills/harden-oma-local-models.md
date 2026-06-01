---
name: harden-oma-local-models
description: Apply patches to the open-multi-agent (OMA) framework to handle local model edge cases like string history crashes and triple-quote JSON parsing errors. Use when preparing upstream PRs or hardening a local OMA fork.
---

# Harden OMA for Local Models

Open-multi-agent (OMA) assumes high-conformity models (like GPT-4 or Claude 3.5). Local MoE models, especially when quantized, can emit malformed JSON or raw string histories that crash the framework.

## Triggers

- Encountering `msg.content.some is not a function` error (string history crash).
- Model falling into "2-Bit Drunk" hallucination loops due to silent `JSON.parse` failures.
- Need to prepare upstream PRs for the OMA framework.

## Procedure

### 1. Guard Against String Histories

In `src/llm/openai-common.ts`, ensure all functions iterating over `msg.content` have array type guards.

**Vulnerable Sites:** `hasToolResults`, `toOpenAIUserMessage`, `toOpenAIAssistantMessage`.

**Fix:**
```typescript
if (typeof msg.content === 'string') return false; // or appropriate fallback
if (!Array.isArray(msg.content)) return false;
```

### 2. Implement Robust Regex Fallback for JSON

Replace silent `JSON.parse` catches with a regex extractor, specifically for single-string parameter tools like `bash` or `run_python_script`.

**Target:** `fromOpenAICompletion` in `src/llm/openai-common.ts`.

**Fix Pattern:**
```typescript
} catch {
  const args = toolCall.function.arguments.trim();
  const name = toolCall.function.name;
  if (name === 'run_python_script' || name === 'bash') {
    const paramName = name === 'run_python_script' ? 'code' : 'command';
    const regex = new RegExp(`\{\s*"${paramName}"\s*:\s*([\s\S]*?)\s*\}$`);
    const match = args.match(regex);
    if (match) {
      let val = match[1]!.trim();
      // Strip unescaped triple quotes commonly emitted by MoE models
      if (val.startsWith('"""') && val.endsWith('"""')) val = val.slice(3, -3);
      else if (val.startsWith("'''") && val.endsWith("'''")) val = val.slice(3, -3);
      parsedInput = { [paramName]: val };
    }
  }
}
```

### 3. Fix Cumulative Telemetry

In `src/llm/openai.ts`, ensure `inputTokens` are assigned directly from the chunk usage rather than compounded recursively.

```typescript
if (chunk.usage !== null && chunk.usage !== undefined) {
  inputTokens = chunk.usage.prompt_tokens;
  outputTokens = chunk.usage.completion_tokens;
}
```

## Pitfalls and Fixes

- **Silent Failures:** Returning an empty `{}` on parse failure causes model loops. Always attempt a regex fallback or return a descriptive error.
- **Multiple Call Sites:** Ensure type guards are applied to ALL functions handling message content, not just the one currently crashing.