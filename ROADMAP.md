# PROJECT APOLLO ROADMAP: The Sovereign Path

## 🏁 Phase 6: The Architect (COMPLETED)
- [x] **Core Scaffolding**: Unified entry point and modular dispatcher logic.
- [x] **The Vault**: Initial Vector DB integration for persistent knowledge.
- [x] **Infrastructural Sovereignty**: High-speed 420GB `ext4` partition (`AI_Fast`) on NVMe for model paging.

## 📥 Phase 7: The Chronicler & Context Firewall (COMPLETED)
- [x] **Apollo V3.5 Architecture**: Successfully migrated routing to Qwen3.5 family.
- [x] **Gatekeeper Precision Engineering**: Standardized on Qwen 3.5 4B "Aggressive" with JSON schema triage.
- [x] **Context Firewall (Triage Hook)**: Implemented native Gemini CLI hook to intercept large data transfers.
- [x] **Gmail Ingestion**: Indexed 160k+ emails into the Vector DB for long-term memory.

## 👁️ Phase 8: The Oracle & The Model Hoard (COMPLETED)
- [x] **Visual Inventory System**: Auto-detect tools via Qwen2.5-VL and diff against JSON Vault.
- [x] **Live Telemetry**: Real-time dashboard for GPU/CPU/3D Printer status (Apollo Glass Cockpit).
- [x] **The Model Hoard**: Archiving unique, highly-capable open-weight models locally.

## 🛡️ Phase 9: The Sovereign Engine (COMPLETED)
- [x] **Bare-Metal RDNA 4 PyTorch**: Successfully optimized deep-learning backend natively targeting `gfx1201`.
- [x] **Sovereign Training PoC**: Local QLoRA fine-tuning bypassing ROCm/PEFT pinning issues.
- [x] **RDNA 4 MoE Hardware Trace**: Generated 1GB SQLite Perfetto trace proving 62+ TPS hardware capability on Qwen 30B MoE.

## 👁️ Phase 10: The Multimodal Frontier (CURRENT)
- [x] **Unified Vision Core**: Implemented "Desktop Eyes" bridge using native Qwen 3.5 4B-Vision.
- [x] **Resident Loadout Optimization**: Standardized the 16GB VRAM "Sovereign Duo" (9B + 4B Vision).
- [ ] **Autonomous Desktop Navigation**: Integrate "Desktop Eyes" into the agent loop.
- [ ] **Procurement Mind**: Autonomous parsing of email/PDF flyers to track historical pricing.

## 🧠 Phase 11: Biological Memory Architecture (COMPLETED)
- [x] **Virtual Memory Manager (VMM)**: Track token usage and trigger pre-compaction flushes.
- [x] **Deep Sleep Triage (Neocortex)**: Implemented nightly scripts to process `weekly_epiphanies.jsonl` into actionable tasks and core beliefs.
- [x] **Associative Page-In**: Routed summaries into ChromaDB (`shop_vault`) for instant recall.

## 🚀 Phase 12: SOTA Agentic Architecture (COMPLETED)
- [x] **Surgical File Editing:** Built `replace_code` in Toolbox for precise multi-line replacements.
- [x] **Context Window Efficiency:** Added hard `max_lines` truncation to prevent VRAM death spirals.
- [x] **Semantic Delegation:** Built `delegate_task` to spin up isolated, synchronous sub-agents.
- [x] **Parallel Tool Execution:** Train the local model to emit multiple tool JSON blocks in a single turn.
- [x] **Async Shell Commands:** Upgraded `run_shell` with timeouts to prevent hanging.

## 👑 Phase 13: The Sovereign Entity (CURRENT)
*Integrating Anthropic's KAIROS offline orchestration, 1-bit background daemons, and OS-control VLMs.*
- [x] **Offline Orchestration:** Successfully wired Anthropic's flagship `claude-private` CLI to a local Qwen 3.5 35B MoE via `llama-server` on port 8082, unlocking 100% local multi-step routing at 65+ TPS.
- [x] **1-Bit Capabilities:** Benchmarked 1-bit `Bonsai-8B` (130 TPS) via custom PrismML ROCm fork. Confirmed massive structural resilience for background parsing.
- [ ] **The KAIROS Daemon (Daydream):** Implement a continuous background loop utilizing `Bonsai-8B` (port 8083) to process logs, validate JSON schemas, and identify unanswered questions while the user is idle.
- [ ] **The Local Orchestrator:** Clone and modify `JackChen-me/open-multi-agent` (TypeScript) to strip out cloud dependencies and wire its `MessageBus`/`TaskQueue` architecture natively to our 35B model.
- [ ] **Holo3 Integration (The Eyes):** Swap the primary OS-control agent to `Holo3-35B-A3B` (a VLM specifically fine-tuned on Qwen3.5-35B for computer use) to allow the entity to physically drive CachyOS applications natively.
- [ ] **TurboQuant ROCm Kernels:** Wait for upstream `llama.cpp` HIP kernels to support `tq1_0`/`tq2_0` KV caching to unlock native 64k context windows on the 35B model without OOM.
