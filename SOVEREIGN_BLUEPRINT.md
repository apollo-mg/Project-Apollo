# Sovereign Engineering Blueprint: Local Reimplementation of "Claude Code"
**Extraction Date:** March 31, 2026
**Source:** Leaked Anthropic `@anthropic-ai/claude-code@2.1.88` (RE)

## 🏗️ 1. Multi-Agent Orchestration (Coordinator-Worker)

### The Role of the Coordinator
The Coordinator is the "Thinking" layer. It manages the user conversation and orchestrates sub-agents. 

## 🏗️ 1. Multi-Agent Orchestration (Coordinator-Worker)

### The Role of the Coordinator
The Coordinator is the "Thinking" layer. It manages the user conversation and orchestrates sub-agents. 

**Core Directives:**
*   **No Lazy Delegation:** Never say "Based on your research, do X." You must synthesize worker findings into a specific spec (file paths, line numbers, exact logic).
*   **Parallelism is a Superpower:** Launch independent workers (e.g., Research and Test-Finding) in a single turn by calling the `AgentTool` multiple times.
*   **Synthesize Results:** The user only sees your summary. Worker results are internal signals, not conversation partners.
*   **Hardware & Precision Simulation (NEW):** Before proposing low-level mathematical, architectural, or hardware-interfacing changes, the Coordinator MUST explicitly state its assumptions regarding floating-point precision (FP16/BF16) and hardware-specific stability (e.g., RDNA 4 constraints) to prevent "silent" numerical crashes.

### The Agent "Forking" Pattern (Context Management)
**Crucial for local 16GB VRAM hardware:**
When an agent needs to perform a task that will generate high "context noise" (e.g., grepping through 100 files or reading 10 massive logs), it MUST **Fork** itself.
1.  **Inheritance:** The Fork inherits the parent's prompt cache (no latency hit).
2.  **Isolation:** The Fork's tool usage (100k tokens of grep output) **never** returns to the parent's window.
3.  **Return:** The Fork returns only a `<task-notification>` XML block with the final result.

---

## 🧠 2. autoDream: The 4-Phase Consolidation (KAIROS)

The background daemon (Daydream Daemon) runs when the user is idle. 

**Trigger Gates:**
- **Time:** >24 hours since last consolidation.
- **Sessions:** >5 new sessions have occurred.
- **Lock:** Mtime-based lock file to prevent race conditions.

### The Consolidation Prompt (The 4 Phases)
1.  **Orient:** `ls` the memory directory and read the `INDEX.md`.
2.  **Gather:** Grep session transcripts for new signals, error messages, and contradictions.
3.  **Consolidate:** Update topic-specific markdown files. Convert relative dates (e.g., "today") to absolute timestamps.
4.  **Prune & Index:** Update `INDEX.md` (keep <25KB). Remove stale pointers.

---

## 📖 3. Structured Session Memory (Sovereign Equivalent)

Rather than a raw context window, maintain a structured `session-memory.md` file at `~/.apollo/memory/`.

### Mandatory Template Sections:
*   `# Current State`: What is actively being worked on? Immediate next steps.
*   `# Task specification`: What did the user ask to build?
*   `# Files and Functions`: Important files and why they are relevant.
*   `# Errors & Corrections`: Failed approaches that should not be tried again.
*   `# Key Results`: Exact output requested (tables, code snippets).

### Update Logic:
Inject this memory into the prompt after a context "compaction" (truncation). Instruct the model to only update the content *below* the template instructions for each section.

---

## 🛠️ 4. Local Hardware Mapping (Apollo Project)

*   **Primary Logic (Coordinator):** Run on the **AMD RX 9070 XT**. Use Qwen 35B MoE (Quantized).
*   **Worker Logic:** Forked workers for research can run on the **Ryzen 7 CPU** (RAM-only) using a smaller model (e.g., CoPaw-9B) to save VRAM for the Coordinator.
*   **Message Bus:** Implement a lightweight Python `MessageBus` to handle the `<task-notification>` XML exchange between the Coordinator and forked sub-agents.
