# 🚀 Project Apollo: User Guide (Sovereign AI OS)

Welcome to the **Sovereign Path**. This guide details the operation, architecture, and interaction models of Project Apollo—your high-performance, geo-distributed AI orchestration system.

---

## 🏛️ 1. System Architecture: The Two-Node Mesh

Apollo operates as a distributed system across two primary hardware nodes, secured by a **Tailscale Zero-Trust Mesh**.

### 🧠 Control Plane (Pi 5)
*   **Role:** Orchestration, Triage, and User Interface.
*   **IP:** `10.0.0.118`
*   **Key Services:** 
    *   **Forensic Logger:** Monitors the workstation for hardware instabilities.
    *   **The Brain:** Hosts the CLI and manages the project state.
    *   **The Mirror:** Maintains a real-time parity sync with the workstation.

### 🏎️ Data Plane (Workstation)
*   **Role:** High-Performance Compute & Heavy Reasoning.
*   **IP:** `10.0.0.5`
*   **Hardware:** RDNA 4 (RX 9070 XT), 16GB VRAM.
*   **Key Services:** 
    *   **Ollama/vLLM:** The inference engines.
    *   **Live Cockpit:** The FastAPI backend for mobile monitoring.

---

## 🧠 2. The Three Minds (Model Routing)

Apollo uses a tiered reasoning system to maximize the 16GB VRAM ceiling.

| Mind | Model | Role | Trigger |
| :--- | :--- | :--- | :--- |
| **The Lead** | `qwen3.5-9b-heretic` | Project Architect & Scaffolder. | `core/project_lead.py` |
| **The Specialist**| `qwen2.5-coder:14b` | Deep Logic, Debugging, & Code. | `#logic` tag |
| **The Sprinter** | `deepseek-v2:16b` | High-Volume Boilerplate (MoE). | `#vol` tag |
| **The Brain** | `qwen35-9b-highiq` | Conceptual Design & Refinement. | `#design` tag |

---

## 📁 3. Module Directory (The Sovereign Structure)

*   `core/`: The heart. Contains `project_lead.py`, `coding_router.py`, and `llm_interface.py`.
*   `infrastructure/`: The nervous system. `apollo_sync.sh`, `forensic_logger.py`, and system services.
*   `benchmarks/`: The performance lab. `coding_shootout.py` and hardware stress tests.
*   `data/`: The memory. `model_database.json` and the `decision_ledger.json` (The Why).
*   `logs/`: The flight recorder. `forensics.log` and `dashboard.log`.
*   `lib/`: Shared utilities and ABI linkage fixes.

---

## 📟 4. Usage Instructions

### 🏗️ Starting a New Project
Use the **Project Lead** to turn a vague idea into a machine-readable JSON blueprint.
```bash
python3 core/project_lead.py "I want to build a [Project Idea]"
```
*   **Output:** A JSON blueprint in `data/decision_ledger.json` with folder maps and worker assignments.

### 💻 Automated Coding (The Router)
Use the **Coding Router** to automatically select the right model for the task.
```python
# In your prompts, use these tags:
#vol   -> Trigger DeepSeek MoE (Drafting)
#logic -> Trigger Qwen Coder (Logic)
#design -> Trigger Qwen High-IQ (Architecture)
```

### 📱 The Mobile Cockpit
Monitor your system from your phone via the **Bioluminescent Dashboard**.
1.  Ensure **Tailscale** is active on your phone.
2.  Navigate to: `http://10.0.0.5:8080`
3.  **Emergency Stop:** Hold the Red button for 2 seconds to kill all models on the network.

---

## 🕵️ 5. Safety & Forensics

### The Forensic Logger
Running in the background on the Pi 5, this service watches for:
*   **OOM Events:** Catches if a model spills into System RAM.
*   **GPU Crashes:** Logs Xid errors or driver timeouts.
*   **Logs:** All failures are stored in `data/failure_modes.json`.

### Thermal Throttling
The `live_dashboard.py` API includes an **Autonomous Kill Switch**. If your GPU hits **90°C**, it will automatically execute an `emergency_stop()` to protect the RX 9070 XT.

---

## 🛠️ 6. Terminal Cheat Sheet

| Command | Description |
| :--- | :--- |
| `apollo-sync` | Force a parity sync between Pi and Workstation. |
| `apollo-vram` | Quick check of GPU Temp, Power, and VRAM. |
| `apollo-models` | See which models are currently in VRAM. |
| `apollo-stop-all` | Panic button. Kills all local AI processes. |
| `apollo-logs-core` | Tail the core orchestrator output. |

---
*Version 1.0.0 | Compiled by Gemini CLI on March 6, 2026*
