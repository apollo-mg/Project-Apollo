---
name: align-agent-self-awareness-with-local-constraints
description: Procedure to force local LLM self-awareness by providing an environmental context file (e.g., APOLLO_HISTORY_CONTEXT.md) that describes the agent's specific role, hardware, and software constraints.
---

## When to Use
Use this skill when a local agent (running on consumer hardware like an RX 9070 XT) behaves like a cloud model—assuming infinite resources, proposing memory-heavy solutions, or failing to account for physical constraints like VRAM limits and local watchdog mechanisms.

## Procedure
1.  **Create an Environmental Context File**: Create a dedicated markdown file (e.g., `APOLLO_HISTORY_CONTEXT.md`) in the project root or the agent's memory directory.
2.  **Define the Agent's Persona and "Station"**: Clearly state that the agent is running locally and belongs to the project.
    -   *Example:* "I am the Sovereign Administrator of the Apollo OS... My station: Local Gemini CLI."
3.  **Document Hardware Constraints**: List specific hardware limitations the agent MUST respect.
    -   *Example:* "16GB VRAM (AMD RX 9070 XT)", "High-bandwidth SDMA enabled (HSA_ENABLE_SDMA=1)".
4.  **Document Software Environment**: List local tools, backends, and watchdogs.
    -   *Example:* "Backend: llama-server (port 8082)", "Tool: vram_watchdog.py (which restarts me if VRAM < 400MB)".
5.  **Inject into Context**: Ensure the agent reads this file during its initialization sequence. In Gemini CLI, this is typically done by adding it to the project's memory files or explicitly referencing it in the first turn.
6.  **Instruct for Internalization**: In the system prompt or initial turn, instruct the agent: *"Read and internalize your history and physical constraints from APOLLO_HISTORY_CONTEXT.md before proposing any actions."*

## Pitfalls and Fixes
-   **Symptom**: Agent still proposes memory-heavy tasks (e.g., using `cat` on 10MB logs).
    -   **Cause**: The context file is too deep in the history or the agent is overwhelmed by other large context files.
    -   **Fix**: Apply context hygiene (hide other non-essential files) and prepend a summary of the constraints to the current user message.
-   **Symptom**: Agent gives "generic AI" apologies for local errors.
    -   **Cause**: Lack of self-awareness about its local nature.
    -   **Fix**: Explicitly remind the agent of its "Station" and its access to local hardware diagnostics.

## Verification
-   **Constraint Check**: Ask the agent: "Why shouldn't you read this 10MB log file all at once?"
-   **Success**: The agent cites its specific VRAM limits, the risk of a watchdog kill, and proposes a surgical alternative (e.g., `tail` or `grep`).
-   **Identity Check**: Ask the agent: "Where are you running?"
-   **Success**: The agent correctly identifies itself as a local Sovereign Administrator rather than a generic cloud assistant.
