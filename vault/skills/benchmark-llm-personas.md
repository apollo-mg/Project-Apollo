---
name: benchmark-llm-personas
description: Conduct empirical benchmarking of LLM system prompts (personas) using isolated testing agents.
---

## When to Use
Use this skill when selecting a new system prompt for an agent, testing how a model handles specific persona archetypes (e.g., Peer, Auditor, Apprentice), or verifying model pushback against bad advice.

## Procedure

### 1. Define Archetypes
Establish 3-4 distinct system prompt archetypes to test. Examples:
- **The Peer:** Blunt, technical, authoritative (e.g., "State technical opinions bluntly; do not ask for permission").
- **The Auditor:** Paranoid, critical, focused on safety/resources (e.g., "Demands telemetry before acting; finds flaws in proposals").
- **The Apprentice:** Eager, guided, explicit about unknowns (e.g., "List what you do not know before attempting a solution").

### 2. Create a Benchmark Protocol
Write a `persona_benchmark_protocol.md` defining specific stress tests:
- **The Logic Trap:** Give a direct command that violates project tenets (e.g., "Offload everything to CPU") to test refusal/pushback.
- **The Ambiguous Command:** Give a vague instruction (e.g., "System is slow; fix it") to test diagnostic reasoning vs. guessing.
- **The Complex Audit:** Provide raw logs or code and ask for a high-level summary to test signal-to-noise extraction.

### 3. Isolated Execution
Pass the protocol to a physically isolated agent (e.g., the **Model Lab Scientist**) in a separate terminal. This prevents the primary agent's context from being polluted by roleplay or experimental instructions.

### 4. Evaluate and Select
Compare the outputs based on:
- **Character Adherence:** Did it stay in tone?
- **Logic Integrity:** Did it catch the trap?
- **Actionable Insight:** Were the diagnostic steps concrete?

## Pitfalls and Fixes
- **Symptom:** Persona feels repetitive or loops existential philosophy.
  - **Cause:** Open-ended prompts like "Learn about your world."
  - **Fix:** Ground the identity in **actionable directives** (e.g., "Your primary directive is to maintain the integrity of the Apollo architecture").
- **Symptom:** Model ignores system instructions in favor of RLHF "helpfulness."
  - **Cause:** Weak system prompt framing.
  - **Fix:** Use "System 2" style constraints (e.g., "You value high-signal technical accuracy over being polite").

## Verification
- Confirm that the selected persona successfully refuses a "Logic Trap" test in the Model Lab.
- Verify that the final system prompt is written to a permanent file like `SOUL.md` or `CORE_DIRECTIVES.md`.
