# Project Apollo: Sovereign AI OS

**An air-gapped, local-first multi-node Swarm architecture designed for absolute human agency and resilient autonomous orchestration.**

---

## 🛑 The Mission
Project Apollo is a "Sovereign AI" operating system built on the premise that if you don't own the hardware, you don't own the truth. It is designed to run complex, asynchronous, multi-agent workloads entirely locally on consumer-grade and surplus datacenter hardware (like the AMD RX 9070 XT and Nvidia Tesla P100). 

The goal is absolute privacy, deterministic execution, and immunity from the "Censorship Tax" and "Cloud Tax" imposed by proprietary API providers.

## 🏗️ System Architecture (The Distributed Swarm)
Apollo has evolved from a single-node monolithic script into a datacenter-grade distributed orchestration layer. It relies on a decoupled "Architect/Worker" topology connected by a high-speed local database.

### 1. The SQLite Message Bus (The Nervous System)
At the heart of Apollo is the `message_bus_api.py`, backed by a SQLite database running in **WAL (Write-Ahead Logging)** mode. This allows the primary Architect node and dozens of Worker nodes to read and write to the same queue simultaneously without database locking.
* **Atomic Claiming:** Workers poll the queue and claim tasks using `EXCLUSIVE TRANSACTION` locks, guaranteeing zero "Double Claims" even under extreme Thundering Herd stress tests.
* **Hardware Physics Routing:** Tasks define explicit hardware constraints (e.g., `min_context: 32768`, `precision_bits: 4.0`). The Message Bus natively routes heavy logic tasks to high-VRAM nodes (P100) and OS-level tasks to local integrated nodes.

### 2. A2A State-Sync (The Agentic Scratchpad)
To solve the "Split-Brain" problem of distributed file systems, Apollo implements an **Agent-to-Agent (A2A) State-Sync Protocol**. 
Instead of masking hardware boundaries with NFS, the models actively negotiate memory routing over the network:
* **The Push:** The Lead Architect pushes file strings and context to the SQLite `/scratchpad` REST endpoints via FastMCP.
* **The Pull:** The remote Worker daemon claims the task, utilizes its profile-injected system instructions, and executes the `starbuck_read_scratchpad` MCP tool to pull the exact context over the local network before execution.

### 3. Project Starbuck (OS Management Layer)
Apollo can autonomously manage its host Linux environment via `starbuck_daemon.py`. By wrapping native Linux tools (`systemctl`, `journalctl`, `apt`, `pacman`) in strict JSON schemas and exposing them via **FastMCP**, the LLM can safely repair its own infrastructure.
* **YOLO Permission Hierarchy:** Operations are strictly gated by YOLO levels (0 to 3), preventing unauthorized or destructive bare-metal executions without explicit Architect consent.

### 4. The Glass Cockpit
A real-time WebSocket-powered WebUI (`apollo_server.ts`) providing a visual 2D spatial canvas of the Swarm's operations. It actively pipes streaming `stdout` from distributed native Linux shell commands directly to the browser while preserving strict LLM token truncation limits.

## 🛠️ The Hardware Reality & "Battle Scars"
This project serves as a proving ground for **Distributed Inference Optimization** and **ROCm/CUDA Interoperability**.

**Current Fleet:** 
* **The Architect:** AMD Radeon RX 9070 XT (16GB VRAM) / Ryzen 7 5700X3D
* **The Executioner:** Headless Dual-Nvidia Tesla P100 Server (32GB VRAM)

**Engineering Standards Discovered:**
* **Context Bleed Protection:** Raw tool output dumps (like a `tree -L 5` or a 10MB log file) will instantly crash the KV Cache of local LLMs. Apollo strictly enforces RegEx sanitization, truncation layers, and IPC stripping (`<think>` blocks) to prevent "2-Bit Drunk" hallucination loops under high context pressure.
* **Qwen 3.6 & Gemma 4 Dynamics:** Tuned optimal sampling loops (`presence_penalty`, `topK`) for heavily quantized MoE models to maintain structural JSON integrity while maximizing reasoning depth.

## 🚀 The Future: Autonomous Epiphanies
The next phase introduces the **Daydream Daemon v2**—a dual-pass, asynchronous pipeline that processes associative memory triggers while the GPUs are idle, allowing the Swarm to organically synthesize "Epiphanies" and generate its own architectural optimizations overnight.

## 🙏 Acknowledgements & Credits
Project Apollo stands on the shoulders of giants. This Sovereign OS is made possible by the relentless innovation of the open-source AI community:
* **Garry Tan & GBrain:** For the architectural blueprint of the "Self-Wiring Memory Layer." Apollo's Daydream Regex Cascade (deterministic graph wiring) and Librarian Hybrid Search (Vector + BM25 + RRF) are direct implementations of the GBrain methodology, achieving zero-cost memory mapping without LLM overhead.
* **[open-multi-agent](https://github.com/huggingface/open-multi-agent):** For the core TypeScript DAG orchestration and baseline agentic loops (MIT License).
* **@TheTom & AtomicChat:** For the bleeding-edge `llama-cpp-turboquant` and `atomic` forks that achieve extreme KV Cache compression, preventing VRAM meltdowns on consumer hardware.
  * *Academic Citation:* Zandieh et al., "TurboQuant: Extreme KV Cache Quantization" (arXiv:2504.19874, ICLR 2026).
* **SeaWolf-AI & the Qwen Team:** For the localized intelligence of the Qwen series and the Darwin-36B-Opus models (Apache 2.0).
* **Unsloth:** For their phenomenal imatrix and BF16 sources used in advanced model quantization.
* **Anthropic:** For pioneering the open Model Context Protocol (MCP) standard that powers Project Starbuck.

---

## ❓ Frequently Asked Questions (FAQ)

**Q: I already run my own LLM server (vLLM, Ollama, TabbyAPI). Do I have to use your inference stack?**
**A:** Absolutely not. Apollo is fundamentally an *orchestration layer*. While we include automated LLMOps tools (like "The Scientist") specifically tuned for `llama-server` and ROCm, the core TS engine (`apollo_coordinator.ts`) and the subagents communicate exclusively via standard OpenAI-compatible API schemas. As long as your existing inference engine exposes an OpenAI-compatible `/v1/chat/completions` endpoint and supports tool-calling (function calling), you can plug it directly into Apollo's `profiles.yaml`. 

**Q: What models work best with this architecture?**
**A:** Because Apollo heavily utilizes complex, multi-turn tool calling and schema enforcement, you need models with strong structural adherence. 
*   **The Orchestrator:** We strongly recommend **Qwen 3.6 27B** (Dense) or the **Qwopus** variants. They exhibit exceptional tool-calling stability, rarely hallucinate syntax, and survive 15+ turn loops without degrading into "apology loops."
*   **The Edge Workers:** For basic logging or simple regex extractions, smaller 8B or 14B models (like Llama 3 or DeepSeek-R1 14B) are perfectly viable for the remote worker nodes.
*   *Note on Gemma 4:* While fantastic for creative/philosophical reasoning (ideal for the Daydream Daemon), we have found their strict JSON tool-calling capabilities to be currently unreliable for the main orchestration loop.

**Q: How many agents or nodes can run at once?**
**A:** The bottleneck is no longer the database lock. Because Apollo uses an SQLite Message Bus operating in **WAL (Write-Ahead Logging)** mode, you can theoretically have dozens of Worker Daemons polling the queue simultaneously. The true limit is your network latency (for A2A State-Sync file transfers) and your aggregate VRAM limits across the cluster. We currently run a stable dual-node setup (1x 9070 XT Coordinator, 1x Dual-P100 Worker).

**Q: Something broke. Where are the logs?**
**A:** Apollo keeps its logs decentralized based on the service:
*   **Orchestration Logic:** Check the terminal stdout where you launched `apollo_coordinator.ts`.
*   **Message Bus/Worker Issues:** The worker daemons output to stdout, but you can also directly inspect the queue by running `sqlite3 deploy/data/message_bus.db "SELECT * FROM task_queue;"`.
*   **Librarian / Memory Errors:** Ingestion errors are logged to `librarian_ingest.log` in the root directory.
*   **Daydream / Metacognition:** The actual architectural epiphanies are saved directly into `data/actionable_epiphanies.jsonl`.

---
*Developed by Mark | AI Systems Architect | Indianapolis, IN*
