# PROJECT APOLLO ROADMAP: The Sovereign Path

## 🏁 Phase 6: The Architect (COMPLETED)
- [x] **Core Scaffolding**: Unified entry point and modular dispatcher logic.
- [x] **The Vault**: Initial Vector DB integration for persistent knowledge.
- [x] **Librarian Workflow**: PDF and URL ingestion via Discord and CLI.
- [x] **Hardware Alignment**: Native ROCm 7.2 / RDNA 4 (GFX1201) baseline for RX 9070 XT.
- [x] **Performance Tuning**: AITER MLA and TunableOp offline kernels verified.

## 📥 Phase 7: The Chronicler & The V3 Migration (CURRENT)
- [x] **Apollo V3 Architecture**: Successfully migrated the entire routing and execution stack to the Qwen3 family for massive speed and reasoning upgrades.
  - **Gatekeeper (Stage 1):** `qwen2.5:0.5b` (Sub-1B fast routing at ~400 TPS).
  - **Engineer (Stage 2):** `qwen3:8b` (Primary logic workhorse).
  - **Vision:** `qwen3-vl:8b` (Upgraded from 2.5-VL for superior spatial logic).
  - **Specialist:** `deepseek-r1:14b` (Reserved strictly for DEEP_THINK chain-of-thought tasks).
- [x] **Gmail Ingestion**: Index 160k+ emails into the Vector DB for long-term memory (Background `mbsync` daemon actively pulling; currently at 8.3GB).
- [x] **vLLM Batch Processing**: Initial bench successful. Leveraging an AWQ 8B model with vLLM (`--enable-prefix-caching`) to maximize KV cache and efficiently process the massive email backlog once `mbsync` finishes.
- [x] **Temporal Search**: Enable "When did I buy X?" or "What was the spec for Y?" queries (Tool built: `search_emails`).
- [ ] **Contextual Awareness**: Allow Apollo to reference past emails in engineering tasks.

## 👁️ Phase 8: The Oracle (CURRENT)
- [x] **Visual Inventory System**: Auto-detect tools via Qwen2.5-VL and programmatically diff against the JSON Vault.
- [x] **Forensic Hardware ID**: Autonomous 4-turn loop for robust component authentication (Web Search -> Local Vault -> Deductive Weights).
- [x] **Live Telemetry**: Real-time dashboard for GPU/CPU/3D Printer status (Apollo Glass Cockpit built).
- [ ] **Procurement Mind (Deal Hunter)**: Autonomous parsing of email/PDF flyers to track historical pricing of groceries and shop supplies, alerting on "good deals" for items in the Wishlist.
- [ ] **Shadow Mind Swarm**: Build a dedicated multi-GPU cluster (RX 580s) from surplus gear for parallel background tasks.
- [ ] **Advanced Vision**: Refine Qwen2.5-VL for 3D print failure detection (Klipper integration).
- [ ] **Proactive Diagnostics**: Apollo notifies Mark if a build is failing or VRAM is leaking.

## 🛡️ Phase 9: The Sentinel (HARDENING)
- [ ] **Enhanced Approvals**: Biometric or multi-factor confirmation for high-impact commands.
- [ ] **Audit Trails**: High-fidelity logging of all system modifications.
- [ ] **Network Defense**: Autonomous scanning and alerting for local network anomalies.

## 🌌 Beyond: The Sovereign Mind
- [ ] **Distributed Voice Satellites**: Repurpose the Raspberry Pi 5 as a dedicated network microphone/speaker endpoint that streams audio directly to the Apollo GPU server, bypassing local audio routing nightmares for a house-wide "Zoey" bridge.
- [ ] **The Model Hoard**: Actively monitor AI releases and locally archive unique, highly-capable open-weight models to ensure Sovereign independence before corporate policies change or access is revoked.
- [ ] **Local LLM Training**: Fine-tuning models on Mark's specific engineering data.
- [ ] **Autonomous R&D**: Apollo proposes project ideas based on inventory and skills.
