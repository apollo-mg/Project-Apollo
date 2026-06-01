---
name: enforce-orchestrator-output-limits
description: Implement and maintain 2MB string truncation limits for tools in the TypeScript orchestrator (open-multi-agent) to prevent Node.js V8 crashes.
---

## When to Use
Use this skill when adding new shell-interactive tools or debugging performance/stability issues in the `open-multi-agent` orchestrator. This is specifically relevant when agents might inadvertently return massive tool outputs (e.g., `cat` on a `.gguf` file or large `.log`).

## Procedure

### 1. Identify Vulnerable Tools
Locate tool definitions in `engines/open-multi-agent/src/tool/built-in/`.
Priority tools:
- `bash.ts`
- `grep.ts`
- `read-file.ts`

### 2. Implement Truncation Utility
Wrap tool output strings in a truncation function before returning them to the orchestrator core.

```typescript
const MAX_OUTPUT_SIZE = 2 * 1024 * 1024; // 2MB

function sanitizeOutput(output: string): string {
  if (output.length > MAX_OUTPUT_SIZE) {
    const truncated = output.substring(0, MAX_OUTPUT_SIZE);
    return `${truncated}\n\n[ERROR: Output truncated at 2MB to prevent Node.js V8 crash. Use surgical commands like 'tail', 'head', or 'grep' to narrow results.]`;
  }
  return output;
}
```

### 3. Apply to Tool Executors
Apply the sanitizer to the `execute` method of shell-based tools.

### 4. Update System Prompt
In the orchestrator's system prompt (e.g., `examples/apollo_coordinator.ts`), add a hard constraint:
*"IMPORTANT: The system enforces a 2MB truncation limit on tool output. If you encounter truncation, you MUST use 'grep' or 'tail' to extract the specific information you need instead of reading the full file."*

## Pitfalls and Fixes
- **Symptom:** Orchestrator process dies silently with no error message.
  - **Likely Cause:** Node.js V8 `ERR_STRING_TOO_LONG` limit reached before truncation.
  - **Fix:** Move truncation logic earlier in the tool execution lifecycle (before any string concatenation).
- **Symptom:** Agents keep trying to read the same large file repeatedly.
  - **Likely Cause:** The truncation message doesn't explicitly suggest alternative tools.
  - **Fix:** Update the truncation warning to include specific command suggestions (`tail -n 500`, `grep "error"`).

## Verification
1. Run a `bash` tool call that `cat`s a file known to be >2MB (e.g., a large model weight or log file).
2. Verify the orchestrator remains stable.
3. Verify the output contains the first 2MB followed by the explicit truncation warning.

```