# APOLLO LONG-TERM MEMORY
This file stores the current high-level state and verified system truths.

## Current System State
- **Hardware**: AMD Radeon RX 9070 XT (16GB VRAM), Ryzen 7 5700X3D.
- **Backend**: Native ROCm 7.2 (Active/Verified) + Ollama + vLLM.
- **Project Root**: `/home/mark/gemini`.
- **Active Stack (Apollo V3)**:
  - **Gatekeeper:** `qwen3:0.6b` (Fast Triage)
  - **Engineer:** `qwen3:8b` (Primary Logic)
  - **Vision:** `qwen3-vl:8b` (Primary Vision)
  - **Specialist:** `deepseek-r1:14b` / `qwen3-coder:30b`

## Verified Truths
- **ROCm 7.2 Stack**: Fully operational on RDNA 4; PyTorch detected with ROCm backend.
- **V3 Cascading Router**: Successfully implemented. The 0.6B Gatekeeper routes simple tasks at ~400 TPS and escalates complex coding/reasoning to the 8B Engineer, drastically improving responsiveness while maintaining deep logic capabilities.
- **The Architect**: 
    - `Qwen3-Coder:30B`: Verified for "one-shot" structural tasks. Multi-turn is restricted by 16GB VRAM limit.
    - `Coder-Next`: **OOM/Incompatible** with current 16GB VRAM (Requires Shadow Mind Swarm or 24GB+ upgrade).
- **Librarian Workflow**: Active (URL/PDF ingestion).
- **Scaffolder Logic**: Supports Python, Web, Arduino, Rust, Node, and Rust (Manual).
- **Dispatcher**: Tuned for direct tool calls (System 1).
- **The Model Hoard**: Archiving unique open-weight models locally is a core priority to avoid future paywalls/censorship.

## Performance Tuning
- **AITER (ROCm 7.2)**: `amd-aiter` (Triton-Enhanced Runtime) is active, enabling AITER MLA for optimized DeepSeek and Qwen3 inference.
- **Offline Tuning (TunableOp)**: 
    - `tunableop_results0.csv` generated specifically for GFX1201 (RX 9070 XT).
    - **Benchmark**: GEMM (1024x1024) optimized to **0.16ms** using native `hipBLASLt` kernels.
    - **Deployment**: `PYTORCH_TUNABLEOP_ENABLED=1` is now the standard for all Apollo workloads.

## Background Services (Post-Reboot Checklist)
If these do not start automatically, they must be manually triggered:
1. `mbsync.timer`: Systemd user timer for Gmail synchronization.
2. `background_chronicler.py`: Sweeps Maildir into Chroma DB.
3. `discord_bridge.py`: Core UI for vision/agent tasks.
4. `live_dashboard.py`: The Glass Cockpit (Foreground UI).

## Community Pulse
- Check `COMMUNITY_PULSE.md` for the latest r/LocalLLaMA trends and DeepSeek status.

## Ongoing Goals
- Phase 7: The Chronicler (Email ingestion daemon is active; Temporal search implemented).
- Phase 8: Procurement Mind (Deal hunting from emails) and Shadow Mind Swarm (RX 580 cluster build).
- Expanding personalization via the Dossier system.

## System Hardening (March 6, 2026)
- **Control Plane**: Isolated on Raspberry Pi 5 (zoey-sat). Workstation (10.0.0.5) acts as Data Plane.
- **UUID Mounting**: Drives (/media/mark/AI_Fast, etc.) locked via UUID to prevent path drift.
- **Root Partition Relief**: /tmp bind-mounted to AI_Fast (Ext4) to prevent partition choking.
- **vLLM FP8 Breakthrough**: Achieved 198.5 TPS on RX 9070 XT using native RDNA 4 kernels.
- Art Mind Tuning: ComfyUI optimized with PyTorch 2.12.0.dev + ROCm 7.2.

## Ecosystem Research & Nuggets (Q1 2026)
*   **TileLang (High Priority)**: A domain-specific language for forging high-performance kernels. Potentially the ultimate fix for RDNA 4 `hipblasLt` heuristics and broken Triton kernels by writing hardware-native Flash Attention fixes.
*   **Ray + ROCm 7.2**: Distributed computing framework. Ideal for refactoring the Agentic Loop into independent, autoscaling "Actors" (vLLM, Whisper, Flux) sharing a unified VRAM pool.
*   **SkyPilot**: Orchestration for multi-cluster and cloud-failover. Critical for "Geo-Distributed Sovereignty"—enabling failover to AMD cloud instances if local storage/VRAM hits a wall.
*   **Ryzen AI + ROS 2**: Validated robotics bridge. Enables Apollo to interact with the physical world via ROS 2 nodes for perception and actuator control.

