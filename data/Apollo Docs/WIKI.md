# Apollo Sovereign Engine: Architecture Wiki

**Version:** 1.0-STABLE (Distributed Swarm Era)
**Target Hardware:** Heterogeneous Clusters (e.g., AMD RX 9070 XT + Dual Nvidia Tesla P100)

---

## 1. The Sovereign Philosophy
The Apollo Sovereign Engine is a local-first, air-gapped AI orchestrator. It treats intelligence as a localized utility. By decoupling the **Control Plane** (the LLM reasoning and orchestration) from the **Data/Execution Plane** (the physical nodes running the code), Apollo achieves datacenter-grade resilience on consumer hardware. 

---

## 2. Orchestration & Delegation

### The Sovereign Coordinator
Apollo utilizes a **TypeScript-based Directed Acyclic Graph (DAG)** framework (`open-multi-agent`). The Sovereign Coordinator (currently powered by Qwen 3.6 / Qwopus) orchestrates the entire cluster. It does not run bash commands itself; it delegates them.

### The SQLite Message Bus (`message_bus_api.py`)
To coordinate the Swarm, Apollo uses a high-speed SQLite database operating in **WAL (Write-Ahead Logging)** mode.
*   **Atomic Claiming:** Remote Worker daemons poll the queue and claim tasks using `EXCLUSIVE TRANSACTION` locks, completely preventing "Double Claim" bugs during extreme concurrent loads (Thundering Herd).
*   **A2A State-Sync (The Scratchpad):** To solve the "Split-Brain" filesystem problem across multiple physical nodes, subagents use a decentralized scratchpad. The Coordinator *pushes* required context to the Message Bus, and the remote worker *pulls* it via the `starbuck_read_scratchpad` MCP tool over the network.

### The Capability Router (`modules/capability_router.py`)
Tools are treated as an economics problem. The router dynamically evaluates a task's physics (e.g., `min_context: 32768`, `precision_bits: 4.0`) against the active fleet (stored in `vault/hardware_profiles.db`). It guarantees heavy logic tasks hit the high-VRAM nodes (P100s) while basic formatting hits lower-tier edge devices.

---

## 3. The Memory Layer (GBrain Architecture)

Apollo employs a three-tier memory architecture designed to defeat the KV Cache "Memory Wall". The implementation heavily borrows from **Garry Tan's GBrain** methodology—a self-wiring memory layer built for AI agents.

### Hybrid Search & Reciprocal Rank Fusion (Librarian)
The `sovereign_search.py` engine retrieves knowledge by fusing two distinct databases:
1.  **ChromaDB:** Semantic Vector search for conceptual queries.
2.  **SQLite FTS5 (`bm25_index.db`):** Exact keyword search (BM25) for literal strings (e.g., error codes).
Results are merged using Garry Tan's **Reciprocal Rank Fusion (RRF, k=60)** algorithm, ensuring that both semantic meaning and exact keyword hits mathematically bubble to the top of the context window.

### The Seed Vault (Semantic System Prompting)
To prevent massive static system prompts from destroying the GPU's KV cache, Apollo relies on "Semantic System Prompting." Enterprise best practices and API docs are pre-compiled into a distributed `apollo_seed_vault.tar.gz`. The Sovereign Coordinator pulls specific rules dynamically via RAG only when a task requires them.

---

## 4. Autonomy & LLMOps

### The Daydream Daemon v2 (`daydream_v2.py`)
A background pipeline that synthesizes knowledge while the GPUs are idle (monitored via Exponentially Weighted Moving Averages of GPU usage).
*   **Pass 0 (Regex Cascade):** Before the LLM even wakes up, a deterministic regex cascade parses raw agent logs. It automatically wires strict graph edges (e.g., `Modified`, `Read`, `Executed`) into `vault/graph_memory.db` using zero GPU compute.
*   **Pass 1 & 2 (Dreamer & Filter):** The daemon generates architectural epiphanies and uses Native Guided Decoding (GBNF) to strictly evaluate their actionability before appending them to the task queue.

### The Scientist (`modules/the_scientist.py`)
An autonomous LLMOps agent that manages model performance. Utilizing logic pioneered by `raketenkater/llm-server`, it dynamically spins up inference engines, profiles hardware bottlenecks, runs LLM-as-a-Judge evaluations (e.g., checking for TurboQuant asymmetric KV cache corruption), and logs optimal launch flags to the Capability Router's database.

---

## 5. OS Management (Project Starbuck)
Project Starbuck operates via a FastMCP daemon (`starbuck_daemon.py`), granting Apollo structured, schema-validated access to Linux system administration (e.g., `systemctl`, `journalctl`). It is locked behind a strict **YOLO Permission Hierarchy (Levels 0-3)** to prevent destructive bare-metal actions without Architect approval.