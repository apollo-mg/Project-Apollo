# PROJECT JARVIS: Technical Whitepaper
## An Autonomous, High-Reasoning Engineering Assistant with Multi-Model Orchestration

**Author:** Project Jarvis Core / Senior Engineering Peer
**Target Audience:** DevOps, AI Engineers, and Systems Architects
**Date:** February 21, 2026

---

### **1. ABSTRACT**
Project Jarvis is a specialized, autonomous AI agent designed for physical engineering environments. Unlike general-purpose LLMs, Jarvis employs a "Three-Mind" architecture that decouples intent triage from technical reasoning and safety auditing. This paper details the implementation of a "System 2" reasoning loop that cross-references Retrieval-Augmented Generation (RAG) data against internal engineering physics to prevent blind compliance and "poisoned" data ingestion.

---

### **2. ARCHITECTURAL OVERVIEW: THE THREE-MIND MODEL**
The system is built on a heterogeneous model stack orchestrated to fit within a 16GB VRAM envelope (AMD RDNA 4 / ROCm 7.1).

#### **2.1 Mind 1: The Receptionist (System 1 - Intent)**
*   **Model:** Hermes 3 (8B)
*   **Role:** Front-line triage and persona management.
*   **Function:** Classifies user input into `CHAT` (low-latency social) or `WORK` (high-rigor technical). It refines vague human requests into crisp, technical tasks for the Engineer.

#### **2.2 Mind 2: The Engineer (System 2 - Reasoning & Synthesis)**
*   **Model:** DeepSeek-R1 (14B GGUF)
*   **Role:** Tool selection, RAG analysis, and Technical Synthesis.
*   **Function:** Operates in two passes:
    1.  **Selection Pass:** Maps tasks to JSON tool calls (e.g., `query_vault`, `git_commit`).
    2.  **Synthesis Pass:** Analyzes tool outputs for technical accuracy and safety.

#### **2.3 Mind 3: Visual Intelligence (Vision)**
*   **Model:** Qwen2.5-VL
*   **Role:** Spatial awareness and part identification.
*   **Function:** Analyzes webcam and desktop streams to sync physical inventory with digital state.

---

### **3. KNOWLEDGE MANAGEMENT & THE VAULT**
#### **3.1 Retrieval-Augmented Generation (RAG)**
*   **Vector DB:** ChromaDB (Local persistent storage).
*   **Embeddings:** Nomic-Embed-Text v1.5 (8k context window).
*   **Ingestion:** Automated "Micro-Pilot" librarian (`pilot_ingest.py`) with SHA-256 WORM (Write Once, Read Many) integrity checks.

#### **3.2 Grounding & The "Liar Trap" Audit**
To solve the "stochastic parrot" problem where LLMs blindly trust RAG data, Jarvis implements a mandatory **Safety Audit Layer**. If a retrieved document (e.g., a poisoned manual) suggests a physically dangerous action (e.g., 48V for a 12V component), the System 2 Synthesis pass identifies the conflict between the RAG data and internal engineering training, issuing a `⚠️ CRITICAL SAFETY ALERT`.

---

### **4. SYSTEMS ENGINEERING & INFRASTRUCTURE**
#### **4.1 VRAM "Tetris" Orchestration**
Due to the 16GB limit of the RX 9070 XT, Jarvis employs a custom `vram_management.py` module. It proactively unloads System 1/2 models when the Vision model is required, and vice versa, using `keep_alive: 0` API calls to Ollama to ensure zero OOM (Out of Memory) crashes during high-context operations.

#### **4.2 Tool Agency & Version Control**
*   **Local Governance:** Integrated Klipper API for 3D printer telemetry and emergency stops.
*   **Git Lifecycle:** Integrated `git_status`, `git_commit`, and `git_log` for autonomous (yet human-approved) code versioning.
*   **The Dossier:** A centralized `shop_dossier.json` for long-term semantic memory and "pending knowledge" verification.

---

### **5. OPERATIONAL FLOW**
1.  **Input:** User provides voice/text command.
2.  **Triage:** Hermes 3 identifies intent.
3.  **Action:** DeepSeek-R1 selects and executes tools (Vault, Web, Git, GPU).
4.  **Synthesis:** DeepSeek-R1 reviews results for safety/contradictions.
5.  **Persona:** Hermes 3 synthesizes the final response, emphasizing safety flags.

---

### **6. CONCLUSION & FUTURE ROADMAP**
Project Jarvis has achieved a milestone in **Grounded Autonomous Agency**. By moving the "Engineer" behind a "Receptionist," we achieve superior intent accuracy. By adding the "Synthesis" pass, we achieve hardware safety. 

**Phase 6 (The Architect)** will introduce:
*   **Autonomous Project Scaffolding:** Zero-touch repo creation.
*   **CAD/PCB Awareness:** Vision-to-OpenSCAD generation.
*   **Deep-Reasoning CodeGen:** Direct script authoring via R1 reasoning loops.

---
**Repository:** `/media/mark/48B42D2CB42D1DC6/gemini_infrastructure`
**Stack:** Python 3.12, ROCm 7.1.1, Ollama, LangChain, ChromaDB.
