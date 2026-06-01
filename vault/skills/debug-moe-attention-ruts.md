---
name: debug-moe-attention-ruts
description: Procedural diagnosis and mitigation of "Attention Ruts" in quantized MoE models, where the model repeatedly anchors on specific characters (like extra quotes) seen in prior error messages. Use when a local agent gets stuck in a repetitive tool-calling loop despite seeing clear error feedback.
---

# Debugging MoE Attention Ruts

Highly quantized MoE models (e.g., IQ3_M, IQ3_XXS) can suffer from "attention anchoring" where they repeat a specific syntax mistake (like adding an extra quote to a path) after seeing that mistake reflected back in a tool's error message (e.g., `ENOENT: no such file or directory, stat '/path/to/file"'`).

## Diagnosis Workflow

### 1. Identify the Loop
Monitor tool call logs for identical or nearly identical arguments across multiple turns.
- **Signal**: The model receives a clear error message (e.g., "File not found") but repeats the *exact same* incorrect path in the next turn.

### 2. Verify Framework vs. Model
Before assuming a framework bug (like an escaping error in the tool code), verify what the model is *actually* generating.

**Action**: Extract the raw JSON tool call from the logs and test it against the framework's parser in isolation.

```bash
# Example verification script
node -e 'const { parser } = require("./dist/parser.js"); console.log(parser(`{"path": "/src/file\""}`))'
```

If the parser correctly reflects the garbage characters (e.g., the extra `"`), then the framework is working perfectly and the model is hallucinating.

### 3. Mitigation Strategies

#### A. Tool Pivot
If the model is stuck on a specific tool (e.g., `glob`), prompt it to use a more primitive tool (e.g., `bash` with `ls`) to break the attention rut.
- **Trigger**: "You seem stuck in a loop with tool X. Try using bash to verify the file path first."

#### B. Sampling Adjustment
Increase `frequency_penalty` (e.g., to 1.1 or 1.2) to discourage the model from repeating the same tokens.

#### C. Manual Context Reset
If the loop is severe, use `/clear` or manually truncate the conversation history to remove the turns where the error message (the "anchor") is present.

## Verification
- [ ] Check if the model's next tool call matches the expected correct path.
- [ ] Verify if the `frequency_penalty` successfully broke the repetition loop.