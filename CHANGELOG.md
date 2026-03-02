# PROJECT APOLLO: CHANGELOG

## [2026.03.01] - Apollo V3 "Qwen3" Migration
### 🚀 Major Architectural Shift
- **Cascading Router (V3):** Fully implemented the dual-stage dispatch system.
    - **Stage 1 (Gatekeeper):** Migrated from `Llama 3.2 1B` to `Qwen3:0.6B`. Performance verified at ~400+ TPS.
    - **Stage 2 (Engineer):** Standardized on `Qwen3:8B` as the primary logic workhorse.
- **Vision Upgrade:** Migrated from `Qwen2.5-VL` to `Qwen3-VL:8B` for superior OCR and spatial reasoning on RDNA 4.
- **Sovereign Network:** 
    - Established Tailscale mesh between PC-Ubuntu and Pi 5 (Zoey-Sat).
    - Configured Pi 5 as a Subnet Router (10.0.0.0/24) and Exit Node.
    - Resolved PIA VPN "Split Tunnel" conflicts, enabling simultaneous private browsing and local MagicDNS.

### 🛠️ System & Tools
- **The Forge:** Established `modules/forge.py` for structured idea capture. Seeded with "Neural World" and "Imagination-Based Troubleshooting" visions.
- **DeepSeek Scout:** Deployed autonomous monitoring for DeepSeek-V4/R2 releases (4-hour cron cycle).
- **ROCm 7.2:** Verified and standardized stack documentation for RDNA 4 (GFX1201).
- **VRAM Tetris:** Optimized model swap thresholds for 16GB VRAM safety.

### 🧹 Maintenance
- Purged all legacy references to `llama3.2:1b` and `qwen2.5vl` from `GEMINI.md`, `MEMORY.md`, and `SOUL.md`.
- Updated global memory with Qwen3-specific operational standards.
- Manually resumed Gmail sync (9.7GB+ verified) via `repair_and_sync_mail.sh`.

---
*Status: System Unified. VRAM Tetris Optimized. Engineering Mind Active.*
