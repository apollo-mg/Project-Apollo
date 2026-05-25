# APOLLO SOVEREIGN MEMORY
This file is the single source of truth for the Sovereign Engine state, hardware stability, and verified cognitive milestones.

## 🧬 Current System State
- **Hardware**: AMD Radeon RX 9070 XT (16GB VRAM), Ryzen 7 5700X3D.
- **Data Plane (Workstation)**: 10.0.0.5 (Ubuntu 24.04, Kernel 6.17).
- **Control Plane (Pi 5)**: `rpi5workbench` (Isolated CLI/History).
- **Project Root**: `/home/gemini/Project-Apollo`.
- **Primary AI Residency**: llama-server (Port 11435) for agentic loops (62+ TPS).

## 🛡️ RDNA 4 Stability Trinity (gfx1201)
To prevent hard freezes and context-switch hangs during training/inference:
1.  `HSA_ENABLE_SDMA=0`: Disables unstable SDMA on RDNA 4.
2.  `AMDGPU_CWSR_ENABLE=0`: **CRITICAL.** Prevents hardware lockups during 8-bit quantization and context switches.
3.  `HSA_OVERRIDE_GFX_VERSION=12.0.1`: Forces the correct hardware path.

## 🧠 Training & Identity Insights
- **The "Identity Snap"**: Identity shifts (Qwen -> Apollo) are observable at **1 Epoch**. At this level, the model acts as a "Co-Cognitive Peer."
- **Persona Drift**: At **2 Epochs**, the model overfits and "goes wild," hallucinating bizarre identities (e.g., "5-year-old child," "Pi 6 resident").
- **Optimizer Rule**: Use `paged_adamw_32bit` to offload states to system RAM; standard AdamW triggers hangs when targeting MLP layers.
- **Targeting**: To hardcode identity without prompts, target `embed_tokens` and `lm_head` in addition to linear projections.

## 🛠️ Verified Ecosystem Truths
- **BitsAndBytes Fix**: Prepend `/opt/rocm/bin` to `PATH` before `import torch` to ensure Wave32 detection on RDNA 4.
- **vLLM ROCm Kernels**: Standard Qwen 3.5 FP8 models with "unfused" layers may fail; GGUF/Ollama paths are stable.
- **V3 Router**: Gatekeeper (0.6B) routes simple tasks (~400 TPS) and escalates complex logic to Engineer (8B/9B).

## 🚀 Ongoing Objectives
- **Phase 7/8**: The Chronicler (Email ingestion) and Shadow Mind Swarm (RX 580 cluster).
- **Engineering CIC**: Quest 2 spatial terminals using GGUF quants for immersive debugging.
- **v8 Dataset**: Auto-generating future training data from "Ancestral History" (this conversation).

## 📌 Maintenance
- Drives are UUID-locked to `/media/mark/AI_Fast`.
- `/tmp` is bind-mounted to AI_Fast to avoid root partition choking.
- Update `infrastructure/SOVEREIGN_MODEL_INVENTORY.md` after any model move.
