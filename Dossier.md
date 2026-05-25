### **Dossier.md (Rewritten)**

```markdown
# SOVEREIGN DOSSIER: Mark's Operational Playbook

This file defines the physical workflow, network topography, and Agent architecture for the Sovereign Engine.

## 🌐 Network & Workflow Topography
- **The Roaming Terminal**: Mark utilizes a combination of **Termux**, **tmux**, and **Tailscale** to create a persistent, ubiquitous command center.
- **Workflow**: A session can be initiated on the Galaxy S21 (mobile), detached, and re-attached seamlessly from the Workstation (10.0.0.5) or Pi 5 (10.0.0.118) over the Tailscale mesh.
- **Device Roles**:
  - **Galaxy S21**: High-speed compute core; mobile terminal; primary logic interface.
  - **Pi 5 (10.0.0.118)**: The "Golden Source" for memory files; background ingestion; reliable daemon host.
  - **Workstation (10.0.0.5)**: Heavy compute; LLM fine-tuning; massive vector processing.
  - **Fire HD 11**: Workbench telemetry terminal; visual monitor.

## 🤖 The Sovereign Quartet (Agent Architecture)
To prevent context collapse across multiple heavy domains, the system is restricted to four distinct intelligence profiles. Three are specialized, and one is the baseline check.

### 1. Zoey (The Engineer / Apollo)
- **Domain**: Software, AI Systems, Linux, Networking.
- **Focus**: Building the Sovereign OS, managing scripts, handling system operations.

### 2. Vulkan (The Architect / Omni-Shaper)
- **Domain**: Mechanical Engineering, 3D Printing, CAD, Modal Analysis.
- **Focus**: Hardware prototypes, resonance tuning, material science.

### 3. Liara (The Librarian / Shadow Broker)
- **Domain**: Data ingestion, Vector DB management, Historical recall.
- **Focus**: Parsing emails, storing transaction data, answering "When/Where/What" queries from the Vault.

### 4. The Auditor (The Baseline / System Watchdog)
- **Domain**: Context hygiene, prompt drift detection, core logic.
- **Focus**: Periodically reviewing the `MEMORY.md` and `SOUL.md` files of the other agents. It operates with ZERO custom personality or persistent memory. Its sole job is to ensure the other agents haven't "over-personalized" their context into hallucination or performance degradation.

## 📜 Memory Management (The Remote-First Protocol)
- All agents MUST treat the Pi 5 as the definitive source of truth.
- Local memory files on devices like the S21 are Read-Only caches updated at startup.
- Any architectural changes MUST be pushed to the Pi 5 via SSH.

## 🛠️ System Hardening & Tuning
- **The Two-Mind Proposal**: A "Two-Mind" proposal has been identified for the Coding models. This involves using a 'Logic King' (Q6_K dense) for deep reasoning and a 'Speed Demon' (16B MoE sparse) for rapid iteration.
- **PyTorch Build**: The PyTorch build has been completed and verified for the test case.
- **Perfectly Tuned**: The system is now "Perfectly Tuned" and ready for heavy compute.
- **GitHub CLI**: The GitHub CLI (`gh`) has been successfully installed on the Pi 5.

## 📅 Project Decision & Roadmap
- **Alpha Build Guide**: A guide for the 'Alpha Build' has been identified as a relevant reference for the project.
- **Unfulseen Roadmap**: The current roadmap is being reviewed for unfulseen tasks.

## 🗂️ Project Index (Progressive Disclosure)
When discussing specific projects, do not hallucinate details. Instead, use your file reading tool to load the specific project file into context.
- **Omni-Shaper:** `/home/gemini/Project-Apollo/projects/omni_shaper.md` (Contains IMU, telemetry, and 3D printing architecture details).
```

### **PENDING_QUESTIONS.md (Rewritten)**

```markdown
# Pending Questions
1. **Ambiguity**: What's unfulfilled on our roadmap currently?
2. **Ambiguity**: What's the plan for the 'Two-Mind' proposal?
```