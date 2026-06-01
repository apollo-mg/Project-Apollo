---
name: manage-context-hygiene-for-local-models
description: Procedural management of context volume to prevent "Lost in the Middle" syndrome and improve instruction adherence for smaller local models (e.g., 26B-35B).
---

## When to Use
Use this skill when a local model (with 16GB-24GB VRAM limits) starts ignoring system instructions, hallucinating tool parameters, or showing degraded reasoning despite correct configuration. This often happens when the model is overwhelmed by large aggregated context files (e.g., multiple `GEMINI.md` files across different drives).

## Procedure

### 1. Identify Context Overload
Check the volume of system instructions being sent to the model.
- **Symptom:** Model ignores a "CRITICAL" rule placed near the middle or end of the system prompt.
- **Symptom:** High token usage at the very start of a session (e.g., 100k+ tokens for the first turn).

### 2. Rename Global Context Files
Temporarily "hide" global or project-level context files that are not strictly necessary for the current task.
- **Action:** Locate `GEMINI.md` files (check home directory `~/.gemini/` and the current workspace root).
- **Command:** `mv GEMINI.md GEMINI.md.bak`
- **Effect:** This forces the CLI/agent to boot with a blank or minimal memory, ensuring the model's attention is focused solely on the task-specific instructions and tool schemas.

### 3. Session Clearing
For long-running sessions, use internal CLI commands to reset the "moving" context.
- **Command:** `/clear`
- **Effect:** Resets the conversation history while keeping the (now minimized) system instructions.

### 4. Selective Restoring
Once the high-precision task (e.g., a complex code edit or tool-calling sequence) is complete, restore the context files.
- **Command:** `mv GEMINI.md.bak GEMINI.md`

## Pitfalls and Fixes
- **Symptom:** Model forgets the overall project mission or user preferences.
  - **Cause:** Important context was hidden during the hygiene process.
  - **Fix:** Summarize the critical "hidden" context into a single, short paragraph and include it in the user prompt while the files are hidden.

## Verification
- Verify turn-1 token usage is significantly lower (e.g., <10k tokens instead of 140k).
- Confirm the model follows a specific instruction that it was previously ignoring.
- Ensure `GEMINI.md.bak` is present and can be restored.
