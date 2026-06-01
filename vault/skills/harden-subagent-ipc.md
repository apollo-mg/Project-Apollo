---
name: harden-subagent-ipc
description: Procedural hardening of sub-agent Inter-Process Communication (IPC) by stripping internal model tags (like <think> or <|think|>) and collapsing excessive whitespace to prevent context bloat and coordinator confusion. Use when implementing or updating sub-agent tools that return text summaries to a lead orchestrator.
---

# Harden Sub-Agent IPC

When sub-agents (like `codebase_investigator` or `software_engineer`) execute multi-turn loops and return a summary to a lead coordinator, they often leak internal monologues or excessive whitespace that degrades the coordinator's context window.

## Procedural Workflow

### 1. Robust Monologue Stripping
Different models use different tags for reasoning blocks. While standard models use `<think>`, others like Gemma 4 or specific Darwin quants may use `<|think|>`.

**Action:** Implement a regex that handles both optional pipe characters and gracefully handles cases where the model fails to output a closing tag (EOF).

```typescript
// TypeScript Implementation
const cleanSummary = rawOutput
  .replace(/<\|?think\|?>(?:[\s\S]*?<\/think>|[\s\S]*$)/g, '')
  .trim();
```

### 2. Whitespace Compaction
Repeated tool results and multi-turn loops often generate massive vertical whitespace bloat.

**Action:** Collapse three or more consecutive newlines into exactly two.

```typescript
// TypeScript Implementation
const finalSummary = cleanSummary.replace(/\n{3,}/g, '\n\n');
```

### 3. Verification Checklist
- [ ] Test the regex against standard `<think>...</think>` output.
- [ ] Test the regex against Gemma 4 `<|think|>...</think>` output.
- [ ] Test the regex against truncated output where the closing tag is missing.
- [ ] Verify that the IPC payload size is significantly reduced after stripping.

## Pitfalls
- **Greedy Fallback**: Ensure the regex uses `[\s\S]*?` (non-greedy) inside the tags but allows `[\s\S]*$` (greedy to end) if the closing tag is missing.
- **Empty Payloads**: If stripping results in an empty string, provide a meaningful fallback like "Task completed but no final text was provided." to prevent coordinator schema failures.