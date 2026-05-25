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
* **[open-multi-agent](https://github.com/huggingface/open-multi-agent):** For the core TypeScript DAG orchestration and baseline agentic loops (MIT License).
* **@TheTom & AtomicChat:** For the bleeding-edge `llama-cpp-turboquant` and `atomic` forks that achieve extreme KV Cache compression, preventing VRAM meltdowns on consumer hardware.
  * *Academic Citation:* Zandieh et al., "TurboQuant: Extreme KV Cache Quantization" (arXiv:2504.19874, ICLR 2026).
* **SeaWolf-AI & the Qwen Team:** For the localized intelligence of the Qwen series and the Darwin-36B-Opus models (Apache 2.0).
* **Unsloth:** For their phenomenal imatrix and BF16 sources used in advanced model quantization.
* **Anthropic:** For pioneering the open Model Context Protocol (MCP) standard that powers Project Starbuck.

---
*Developed by Mark | AI Systems Architect | Indianapolis, IN*
