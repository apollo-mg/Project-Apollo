---
name: document-for-llm-autonomy
description: Document architectural intent and physical constraints in code specifically to guide future AI agents in maintaining and using the system.
---

## When to Use
Use this skill when writing or refactoring core architectural modules for a "Sovereign Entity" (local AI system). The goal is to make the system "Self-Documenting" for the next agent that opens the file.

## Procedure

### 1. Identify Architectural Intent
Before writing docstrings, define why the code exists and what physical tradeoffs it was designed for (e.g., "Memory-efficient but slow", "High-throughput but requires 16GB VRAM").

### 2. Embed "LLM Agent Instructions"
Add an explicit section in the module-level or class-level docstrings titled `LLM Agent Instructions`. This section should provide direct guidance on how to safely interact with the code.
- **Example:** `When drafting new tools, you MUST define them as a ToolRequirement object here.`

### 3. Define "Physics" Constraints
Clearly document the physical resource requirements or limitations.
- **VRAM/RAM Limits:** "Requires 8GB free VRAM."
- **Context Limits:** "Maximum stable context is 32k with `-ctk q8_0`."
- **Quantization Precision:** "Requires at least 4.0bpw (bit-per-weight) for reliable reasoning."

### 4. Warn about Failure Modes
Explicitly document non-obvious landmines or previous architectural failures.
- **Concurrency Warnings:** "Do NOT attempt to write raw files for inter-agent communication. Always use the MessageBus."
- **Atomic Locks:** "The claim_task() method uses an EXCLUSIVE transaction. Do NOT hold it open during LLM inference."

## Pitfalls and Fixes
- **Symptom:** The next agent ignores the documentation and introduces a regression.
  - **Cause:** The instructions were buried in standard "human" docstrings or were too vague.
  - **Fix:** Use bold headers like `LLM Agent Instructions (CRITICAL)` and keep the instructions concise and imperative.

## Verification
- Ask a local LLM (e.g., the Architect) to read the module and explain the "Architectural Intent" and "Rules for interaction."
- If the model correctly identifies the constraints and rules without a system prompt, the documentation is successful.
