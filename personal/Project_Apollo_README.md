# Project Apollo: Sovereign AI OS

**An air-gapped, local MoE swarm and routing architecture designed for absolute human agency, bypassing centralized data aggregators and cloud-compute monopolies.**

---

## 🛑 The Mission
Project Apollo is not a wrapper. It is a "Sovereign AI" operating system built on the premise that if you don't own the hardware, you don't own the truth. It is designed to run 30B+ Mixture of Expert (MoE) models, Vision models, and RAG pipelines entirely locally on consumer-grade hardware. 

The goal is absolute privacy, deterministic execution, and immunity from the "Censorship Tax" and "Cloud Tax" imposed by proprietary API providers. 

## 🏗️ System Architecture ("Three-Mind / VRAM Tetris")
Apollo uses a cascaded, intent-based routing system to dynamically load and unload specialized models into memory based on the task, maximizing the utility of a strict 16GB VRAM ceiling.

1. **Gatekeeper (System 1):** `qwen3:0.6b` (Resident). Handles fast triage, intent classification, and chitchat at ~400 TPS.
2. **Engineer (System 2):** `qwen3:8b` (On-Demand). The primary logic workhorse for 90% of local tool execution and context gathering.
3. **Specialist (System 3):** `deepseek-r1:14b` / `qwen3-coder:30b` (On-Demand). Deep reasoning, complex structural logic, and agentic orchestration.
4. **Vision:** `qwen3-vl:8b` (Native ROCm). Multi-modal physical world and desktop analysis.

## 🛠️ The Hardware Reality & "Battle Scars"
Building local AI on bare-metal AMD means fighting the Linux kernel and the ROCm stack. This project serves as a proving ground for **VRAM Management** and **Hardware Inference Optimization**.

**Hardware Stack:** 
* AMD Radeon RX 9070 XT (16GB VRAM) / Ryzen 7 5700X3D
* Ubuntu 22.04 / ROCm 7.2 / PyTorch 2.12.0.dev

**ROCm & VRAM Engineering Standards Discovered:**
* **Host-to-Device Transfer Safety:** Forced `.contiguous()` commands on all H2D tensor transfers to prevent silent memory fragmentation and driver hangs.
* **Math Attention:** Enforced `enable_math=True` in SDPA (Scaled Dot-Product Attention) to maintain stability on the RDNA 4 architecture.
* **Deterministic VRAM Sweeps:** Engineered a strict `vram_management.py` protocol that verifies an 8GB+ memory release *before* allowing the router to trigger a model swap, eliminating Out-Of-Memory (OOM) kernel panics.
* **Multi-Turn Vision Protection:** Visual inventory pipelines utilize a strict 2-turn sequence to prevent VRAM crashes: Turn 1 (Qwen3-VL) generates raw text arrays; Turn 2 (DeepSeek-R1) executes programmatic JSON diffs against local databases, bypassing LLM hallucinations and saving memory.
* **Performance Tuning:** Bypassed `rocm-smi` safety locks to increase GPU power limit by +10% (`echo "334400000" | sudo tee /sys/class/drm/card1/device/hwmon/hwmon*/power1_cap`) and enabled `PYTORCH_TUNABLEOP_ENABLED=1` for GFX1201 optimization.

## 📂 Core Pipelines (Proof of Work)

### 1. The "Librarian" RAG Workflow (`librarian_ingest.py`)
An autonomous, zero-trust data ingestion pipeline. It scrapes URLs and local PDFs, chunks the data, generates local embeddings, and stores them in a local Vector Database (ChromaDB). This is a foundational "Proprietary Data Moat" architecture designed to run without sending a single byte to an external server.

### 2. Forensic Hardware ID Pipeline
A highly structured, 4-turn autonomous loop utilizing `Qwen3-VL` (Vision) and `DeepSeek-R1` (Reasoning) to visually identify obscure hardware components, cross-reference them against local specs, and output structured JSON, all within the 16GB VRAM limit.

### 3. The Apollo Dispatcher (`modules/router.py`)
A fast, intent-classification engine that allows the Gatekeeper model to programmatically trigger specific Python modules (Filesystem, Config, Tool Registry) based on the user's natural language input.

## 🚀 The Future: The Post-Bubble Roadmap
Apollo is currently navigating the limits of PCIe bandwidth and ROCm driver fragmentation. The next phase of architecture involves migrating these pipelines off monolithic GPU structures and onto **RISC-V Scale-Out architectures (Tenstorrent TT-Metalium)** to achieve true, deterministic "Shadow Mind" swarms via NoC (Network-on-Chip) routing. 

---
*Developed by Mark | AI Systems Architect | Indianapolis, IN*
