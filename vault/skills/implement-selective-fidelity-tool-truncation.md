---
name: implement-selective-fidelity-tool-truncation
description: Procedure to implement a multi-tiered "Selective Fidelity" algorithm for tool output truncation. Use when blind character chops lose critical data (like error messages at the end of a log).
---

# Implement Selective Fidelity Tool Truncation

This skill describes how to implement an algorithmic, zero-token-cost strategy for compressing massive tool outputs (e.g., from `bash` or `grep`) before they reach the agent's context window. This preserves both the initial context (the "head") and the critical exit state (the "tail").

## Procedure

1. **Establish Tiers**:
   Implement a three-tier logic in the tool's output builder (e.g., `bash.ts` or `read-file.ts`).

2. **Tier 1: Verbatim Pass-Through**:
   If the total output is small (e.g., < 2,000 characters), return it exactly as is. Smaller models can easily parse this without compression.

3. **Tier 2: Line-Based Compression (Standard Logs)**:
   If the output exceeds the threshold and contains multiple lines:
   - Extract the first 50 lines (The "Entry Context").
   - Extract the last 50 lines (The "Exit State" / Errors).
   - Calculate the number of omitted lines.
   - **Mechanism**: Join them with a clear marker: `

... [X lines omitted for context compression. Use grep to search specific patterns] ...

`.

4. **Tier 3: Character-Based Compression (Wide Blobs)**:
   If the output exceeds the threshold but has few lines (e.g., a massive single-line JSON dump or base64 string):
   - Perform a strict character split.
   - Extract the first 1,000 characters.
   - Extract the last 1,000 characters.
   - Join with the `[TRUNCATED]` marker.

5. **Pure TypeScript Implementation**:
   Implement this logic directly in the framework's source code (e.g., `src/tool/built-in/bash.ts`). This ensures the compression happens before any tokens are spent on the LLM or any VRAM is allocated for context.

## Verification Checklist

- [ ] Run a `bash` command that generates 100,000+ characters of output (e.g., `find /`).
- [ ] Verify that the terminal output displays the first 50 lines, followed by the "lines omitted" marker, followed by the final 50 lines.
- [ ] Confirm that if a command results in an error at the very end of a long log, that error is visible to the agent after truncation.

## Pitfalls

- **Blind Chops**: Avoid using `.substring(0, MAX_LENGTH)`. This is a "bandaid on an arterial bleed" and almost always cuts off the most important part: the error message at the end of the log.
- **Marker Recognition**: Ensure the marker is descriptive enough to tell the agent *how* to see the missing data (e.g., suggesting `grep` or `tail`).
