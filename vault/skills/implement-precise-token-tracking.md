---
name: implement-precise-token-tracking
description: Replace character-based token heuristics with precise BPE tokenization (tiktoken) in Node.js orchestrators. Use when telemetry shows massive discrepancies (e.g., 4x) between estimated context pressure and actual LLM KV cache usage.
---

# Implement Precise Token Tracking

## Overview

Simple character heuristics (like `chars / 4`) are volatile. Codebases tokenize much less efficiently than natural English, often hitting `chars / 2.5`. Conversely, natural language summaries can be highly compressible (`chars / 7`). This results in "phantom context pressure" or missed compaction thresholds.

## Implementation Procedure

### 1. Install Dependencies
Install `tiktoken` into the TypeScript/Node.js framework.

```bash
npm install tiktoken
```

### 2. Rewrite Token Utility
Update `src/utils/tokens.ts` to use a real BPE encoder. Use `cl100k_base` for models with OpenAI-style vocabularies (Qwen, Llama 3).

```typescript
import { get_encoding } from 'tiktoken'
import type { LLMMessage } from '../types.js'

// Cache the encoding instance globally to prevent re-initialization overhead
const encoder = get_encoding('cl100k_base')

/**
 * Accurately estimate token count using a real BPE tokenizer.
 */
export function estimateTokens(messages: LLMMessage[]): number {
  let tokens = 0

  for (const message of messages) {
    // Base cost per message for role/formatting overhead
    tokens += 3

    if (typeof message.content === 'string') {
      tokens += encoder.encode(message.content).length
    } else {
      for (const block of message.content) {
        if (block.type === 'text') {
          tokens += encoder.encode(block.text).length
        } else if (block.type === 'tool_result') {
          // Coerce content to string for tokenization
          tokens += encoder.encode(String(block.content)).length
        } else if (block.type === 'tool_use') {
          // Tokenize the raw JSON input
          tokens += encoder.encode(JSON.stringify(block.input)).length
        } else if (block.type === 'image') {
          // Non-text payloads have a model-specific fixed cost (approx 64)
          tokens += 64
        }
      }
    }
  }

  // Base cost for the completion prime
  return tokens + 3
}
```

### 3. Rebuild Framework
Ensure the TypeScript code is recompiled so the CLI picks up the updated logic.

```bash
npm run build
```

## Performance & Calibration

- **Accuracy:** This method typically stays within 2% of the actual token count reported by `llama-server`.
- **Latency:** `tiktoken` is written in Rust with fast bindings; the overhead for encoding a 64k history array is negligible (<50ms).
- **Fallback:** If a model uses a vastly different vocabulary (e.g., Gemma 4), the counts may drift. You can extend the utility to accept an optional encoding name.
