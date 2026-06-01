---
name: diagnose-subagent-parser-failures
description: Diagnose and fix "no final text" or empty report errors from sub-agents (codebase_investigator, software_engineer) by testing the tool parser in isolation and hardening IPC regex.
---

# Diagnose Sub-agent Parser Failures

Use this skill when a sub-agent completes its task but returns an empty response to the Coordinator, or when you suspect a model is stuck in an "Attention Rut" (repetitive tool-calling mistakes).

## 1. Isolate the Model Output
Locate the raw log of the sub-agent's run (usually in `chat_history/`). Find the last turn where the model should have returned its final summary.

## 2. Test Parser in Isolation
To verify if the issue is in the model's output or the framework's parser, run the `text-tool-extractor.js` against the raw text found in the log.

```bash
# From the open-multi-agent-upstream directory
node -e 'const { extractToolCallsFromText } = require("./dist/tool/text-tool-extractor.js"); \
const rawOutput = `PASTE_RAW_MODEL_OUTPUT_HERE`; \
console.log(JSON.stringify(extractToolCallsFromText(rawOutput, ["TOOL_NAME"]), null, 2))'
```

If the output is `[]`, the parser failed to find the tool call. Check for escaped quotes or malformed JSON.

## 3. Harden IPC Stripping
If the parser works but the Coordinator receives "no final text provided", verify the regex stripping in the sub-agent's tool implementation (e.g., `src/tool/built-in/codebase-investigator.ts`).

**Regex for Tag Support (`<think>` and `<|think|>`)**:
```typescript
finalOutput.replace(/<\|?think\|?>(?:[\s\S]*?<\/think>|[\s\S]*$)/g, '').trim()
```

**Whitespace Collapse**:
Always collapse excessive newlines to prevent IPC bloat and "Lost in the Middle" issues for the Coordinator.
```typescript
finalSummary = finalSummary.replace(/\n{3,}/g, '\n\n')
```

## 4. Identify "Attention Ruts"
If the model repeatedly makes the same tool-calling mistake (e.g., adding an extra quote `"` to a path) despite seeing error feedback:
- **Cause**: The model's attention is anchored on the quoted path seen in the previous error message.
- **Diagnostic**: Verify if the error message contains the literal string the model is hallucinating.
- **Mitigation**: Switch to a more flexible tool (e.g., `bash` instead of `glob`) or increase temperature to break the attention anchor.