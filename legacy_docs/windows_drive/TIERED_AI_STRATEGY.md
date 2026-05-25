# Tiered AI Strategy: "The Supervisor Model"

This document defines the rules of engagement for using the Local Agent (DeepSeek) versus the Cloud Agent (Gemini). The goal is to maximize **Token Efficiency** (saving cloud costs) while maintaining **Engineering Integrity** (safety and correctness).

## The Hierarchy

### Tier 3: The "Grunt" (Local Agent)
*   **Model:** DeepSeek-Coder-V2-Lite (Local via LM Studio)
*   **Cost:** $0.00 / 0 Tokens
*   **Speed:** Fast
*   **Role:** Raw data processing, drafting, and rote tasks.
*   **Use Cases:**
    *   **Log Analysis:** "Summarize this 5,000-line `klippy.log` and find the first error." (Saves massive context tokens).
    *   **Boilerplate Code:** "Write a basic Klipper macro skeleton for a fan cycle."
    *   **Math/Geometry:** "Generate an OpenSCAD script for a 20mm cube with a 5mm hole."
    *   **Formatting:** "Convert this CSV to a Markdown table."
*   **Risk:** High hallucination potential. **MUST be verified.**

### Tier 2: The "Hybrid" (Supervisor Loop)
*   **Model:** Local Agent (Draft) -> Gemini (Verify)
*   **Cost:** Low (Only the "Verification" tokens are used)
*   **Role:** Quality Control and Refinement.
*   **Workflow:**
    1.  Gemini prompts Local Agent: "Draft a macro to park the toolhead."
    2.  Local Agent returns code.
    3.  Gemini reviews code against `printer.cfg` constraints (e.g., "Wait, max X is 248, not 300").
    4.  Gemini fixes the code and presents it to the User.
*   **Use Cases:**
    *   Config edits.
    *   OpenSCAD part design (checking fitment).
    *   Scripting (PowerShell/Python).

### Tier 1: The "Architect" (Gemini Cloud)
*   **Model:** Gemini 2.0 Flash/Pro
*   **Cost:** Standard Token Usage
*   **Role:** Strategy, Safety, and Complex Reasoning.
*   **Use Cases:**
    *   **Root Cause Analysis:** Synthesizing multiple data points (logs + user photos + physics).
    *   **Safety Critical:** Modifying electrical currents, voltage settings (48V), or thermal limits.
    *   **Project Management:** Maintaining `GEMINI.md`, planning roadmaps, and deciding *which* agent to use.

## The "Supervisor" Logic (How Gemini Decides)

When the User presents a task, Gemini evaluates it:

1.  **Is it "Safety Critical"?**
    *   *Yes (e.g., changing heater max_power):* **Tier 1 (Gemini Only).**
    *   *No:* Proceed.

2.  **Does it hit the Risk Matrix (INFRASTRUCTURE_CONTEXT Section 5)?**
    *   *Yes:* **MANDATORY WEB SEARCH.** Verify feasibility and find community success/failure reports. Present as **[EXPERIMENTAL]** with a clear Sunk-Cost fallback plan.
    *   *No:* Proceed.

3.  **Is the Context Heavy?**
    *   *Yes (e.g., analyzing a 2MB log file):* **Tier 3 (Delegate to Local).** Gemini writes a script to feed the file to the local agent, then reads the summary.
    *   *No:* Proceed.

3.  **Is it a "Known Solved" pattern?**
    *   *Yes (e.g., standard macros):* **Tier 2 (Hybrid).** Let Local draft it, Gemini polishes it.
    *   *No (e.g., unique failure mode):* **Tier 1 (Gemini).**

## Implementation Status

*   [x] **Local Hook:** `local_agent.ps1` (Basic Query)
*   [x] **Memory:** Session history enabled (`-HistoryPath`).
*   [ ] **Supervisor Script:** Need a wrapper to automate the "Draft -> Verify" loop.
