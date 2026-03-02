# Project Apollo: Sovereign AI OS

**An air-gapped, local MoE swarm and routing architecture designed for absolute human agency, bypassing centralized data aggregators and cloud-compute monopolies.**

---

## 🛑 The Mission
Project Apollo is a "Sovereign AI" operating system built on the premise that if you don't own the hardware, you don't own the truth. It is designed to run 30B+ Mixture of Expert (MoE) models, Vision models, and RAG pipelines entirely locally on consumer-grade hardware. 

The goal is absolute privacy, deterministic execution, and immunity from the "Censorship Tax" and "Cloud Tax" imposed by proprietary API providers. 

## 🏗️ System Architecture ("Three-Mind / VRAM Tetris")
Apollo uses a cascaded, intent-based routing system to dynamically load and unload specialized models into memory based on the task, maximizing the utility of a strict 16GB VRAM ceiling.

1. **Gatekeeper (System 1):** `qwen3:0.6b` (Resident). Handles fast triage, intent classification, and chitchat.
2. **Engineer (System 2):** `qwen3:8b` (On-Demand). The primary logic workhorse for 90% of local tool execution and context gathering.
3. **Architect (System 1.5):** `qwen3-coder:30b` (On-Demand). Complex structural logic, CAD design, and deep reasoning.
4. **Reasoning Specialist:** `deepseek-r1:14b` (On-Demand). High-fidelity chain-of-thought logic.
5. **Vision:** `qwen3-vl:8b` (Native ROCm). Multi-modal physical world and desktop analysis.

## 📂 Core Features & Achievement Proofs

### 1. Multi-Tier Agent Orchestration
Architected a three-stage cascading dispatcher (`modules/router.py`) that programmatically triggers Python modules based on natural language intent, optimizing token generation speed vs. model parameter depth.

### 2. VRAM Resource Management ("VRAM Tetris")
Engineered a strict hardware-aware protocol (`vram_management.py`) that monitors GPU health and verifies memory release before allowing the router to trigger a model swap, eliminating kernel panics on the ROCm 7.2 stack.

### 3. The "Librarian" Local RAG
An autonomous data ingestion pipeline (`librarian_ingest.py`) that scrapes URLs and PDFs into a local ChromaDB Vector Database for semantic retrieval, providing a completely private knowledge base.

### 4. The Forge
A structured two-layered system (`modules/forge.py`) for capturing raw engineering visions and autonomously refining them into executable project proposals using the 30B Architect.

### 5. Discord UI Bridge
A custom Discord bot integration (`discord_bridge.py`) acting as the primary UI, featuring real-time hardware telemetry dashboards, image ingestion for physical inventory audits, and an interactive security approval queue.

## 🛠️ Hardware Requirements
* **Primary Host:** AMD Radeon RX 9070 XT (16GB VRAM) / Ryzen 7 5700X3D
* **Stack:** Ubuntu 22.04 / ROCm 7.2 / PyTorch 2.12.0.dev
* **Backend:** Ollama (Native ROCm) / vLLM

## 🚀 Getting Started
1. Clone the repository.
2. Set up your `.env` file based on `.env.example`.
3. Ensure ROCm 7.2 is configured on your local machine.
4. Run `python3 apollo.py` or start the Discord bridge with `python3 discord_bridge.py`.

---
*Developed by Mark | Lead AI Systems Architect*
