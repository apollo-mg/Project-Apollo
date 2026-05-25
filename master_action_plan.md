# Master Action Plan: Sovereign Entity Architecture (SEA)

## Executive Summary
This Master Action Plan serves as the definitive engineering roadmap for the transition from a fragmented, script-based environment to a unified, hardware-aware, and cognitively tiered Sovereign Entity. The plan is organized into four distinct phases, moving from foundational stability to advanced cognitive autonomy.

---

## PHASE 1: FOUNDATION & PROVENANCE (The Hardware-Software Anchor)
*Goal: Stabilize the computational substrate and lock the environment to prevent "Ghost" configurations and silent data corruption.*

### 1.1 Infrastructure Provenance Protocol
- [COMPLETED] **Task 1.1.1:** Create `scripts/generate_provenance_manifest.sh` to capture `rocminfo`, `clinfo`, `lsmod`, and `pip freeze`.
- [COMPLETED] **Task 1.1.2:** Implement `vault/provenance_manifest.json` to serve as the "Ground Truth" for all future environment rebuilds.
- [COMPLETED] **Task 1.1.3:** Implement the "Driver-Kernel Alignment" check to ensure ROCm/HIP versions match the kernel driver.

### 1.2 Hardware-Level Stabilization (The "RMS Norm" Fix)
- [COMPLETED] **Task 1.2.1:** Implement the "Kernel Synchronization Barrier" by injecting `hipDeviceSynchronize()` and `hipGetLastError()` checks into all custom HIP/C++ kernel calls.
- [COMPLETED] **Task 1.2.2:** Enforce environment variables `AMD_SERIALIZE_KERNEL=3` and `TORCH_USE_HIP_DSA` in the `bootstrap_apollo.sh` script to prevent silent data corruption in the `chroma_db`.

### 1.3 Parameterized Orchestration (The "Anti-Script" Move)
- [COMPLETED] **Task 1.3.1:** Deprecate all `start_*.sh` scripts.
- [COMPLETED] **Task 1.3.2:** Implement `orchestrator.py` using a `profiles.json` schema to manage model profiles, ports, and environment variables (e.g., `HSA_OVERRIDE_GFX_VERSION`).

---

## PHASE 2: UNIFIED ABSTRACTION (The Nervous System)
*Goal: Replace manual overrides with a unified, hardware-aware middleware layer.*

### 2.1 Unified Interface Middleware (UIM)
- [COMPLETED] **Task 2.1.1:** Refactor `llm_interface.py` to accept a `DeploymentConfig` object instead of hardcoded URLs.
- [COMPLETED] **Task 2.1.2:** Implement the `HardwareOrchestrator` to wrap all physical adjustments (audio gain, camera exposure, etc.) into a single API.

### 2.2 Virtual File System (VFS) & Path Resolution
- [COMPLETED] **Task 2.2.1:** Implement `src/vfs/VFSManager.ts` to unify `StandardFS` and `VaultDriver` access.
- [COMPLETED] **Task 2.2.2:** Refactor `list_dir`, `file_read`, and `file_write` to use the VFS, eliminating "Contextual Blindness" and silent path-resolution errors.

### 2.3 Model-to-Hardware Alignment (MHA)
- [COMPLETED] **Task 2.3.1:** Implement the `MHA` logic in the `Agent` initialization to compare `ModelResourceRequirements` against real-time `availableVRAM`.
- [COMPLETED] **Task 2.3.2:** Implement the "Auto-Fallback" mechanism to switch to hardware-aligned models (e.g., SDXL-Turbo) when VRAM margins are breached.

---

## PHASE 3: COGNITIVE INTELLIGENCE (The Brain)
*Goal: Implement tiered intelligence and structured memory to manage the "Cognitive Load."*

### 3.1 The Cognitive Dispatcher (Tiered Intelligence)
- [COMPLETED] **Task 3.1.1:** Implement `modules/cognitive_dispatcher.py` to route tasks between the **Architect Tier** (Deliberative/High-Cap) and the **Worker Tier** (Reactive/Low-Cap).
- [COMPLETED] **Task 3.1.2:** Implement the "Kinetic Validation" protocol to prevent "Political Turbulence" (unnecessary scaling) by auditing the complexity-to-precision ratio of requests.

### 3.2 Tiered Memory & The Librarian
- [COMPLETED] **Task 3.2.1:** Implement the "Tiered Memory System":
    - **Tier 1 (Working Buffer):** In-memory sliding window.
    - **Tier 2 (Associative Cache):** SQLite/Vector-based short-term memory.
    - **Tier 3 (Long-Term Knowledge):** The `vault/` ChromaDB.
- [FAILED] **Task 3.2.2:** Implement the "Truth-Lock" protocol in `modules/vdb.py` to distinguish between `status: "pending"` (unverified) and `status: "verified"` (core dossier) knowledge.

### 3.3 The Prior-Validation Layer (PVL)
- [COMPLETED] **Task 3.3.1:** Implement `modules/pvl_engine.py` to detect "High-Risk Contexts" (e.g., known hallucination triggers) and inject "Anti-Prior" instructions into the system prompt.

---

## PHASE 4: RESILIENCE & AUTONOMY (The Sovereign Entity)
*Goal: Transition from "Command Execution" to "Reflexive Autonomy."*

### 4.1 The Reflex Arc (Error-to-Model Feedback)
- [COMPLETED] **Task 4.1.1:** Implement the `<sensory_input>` XML wrapper in `modules/agent_session.py` to formalize error-to-model feedback.
- [COMPLETED] **Task 4.1.2:** Implement "Cognitive Escalation" to trigger Deep Reasoning (e.g., DeepSeek-R1) when critical system/hardware errors are detected.

### 4.2 Resilience Engineering (Source-Level Mastery)
- [COMPLETED] **Task 4.2.1:** Implement the "Resilience Engineering" protocol, treating source-level patches (e.g., `liberated_vllm`) as formal architectural decisions rather than "workarounds."
- [COMPLETED] **Task 4.2.2:** Implement the "Mutation Guard" in `integrity_layer.py` to distinguish between "Self-Correction" and "Systemic Mutation" during code-writing tasks.

### 4.3 Fleet Orchestration (The Lifecycle Loop)
- [COMPLETED] **Task 4.3.1:** Implement `fleet_orchestrator.py` to automate the **Boot $\rightarrow$ Train $\rightarrow$ Zip $\rightarrow$ Upload $\rightarrow$ Verify** lifecycle for new intelligence assets.

---

**END OF MASTER ACTION PLAN**
