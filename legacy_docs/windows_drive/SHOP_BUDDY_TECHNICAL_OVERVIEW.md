# Technical Overview: Project "Shop Buddy"
**Date:** February 14, 2026
**Status:** Phase 3 Infrastructure Stabilized
**Hardware Target:** AMD RDNA 4 (RX 9070 XT) / Ubuntu 22.04

---

## 1. Executive Summary
"Shop Buddy" is an autonomous engineering partner designed to operate at the intersection of local LLM reasoning and physical shop hardware (3D Printers, GPU Clusters). Unlike standard assistants, it operates under a **Zero-Hallucination Mandate**, requiring empirical grounding via tool-calling for all technical specifications.

## 2. The Three-Mind Architecture
To ensure reliability on a 16GB VRAM budget, the system employs a tiered cognitive strategy:
*   **The Compliance Mind (Llama 3.2):** High-speed grounding and JSON extraction. It acts as a "bouncer," ensuring user intent is translated into valid tool calls.
*   **The Reasoning Mind (DeepSeek-R1 14B):** High-logic engineering "brain." It handles complex physics, CAD strategy, and troubleshooting.
*   **The Grounding Mind (Web/Vault/Sensors):** Real-time verification layer that cross-references all technical claims against the internet or local datasheets.

## 3. Key Achievements & Milestones
### **Infrastructure & VRAM Orchestration**
*   Developed a proactive VRAM manager that unloads heavy ComfyUI/Flux models to make room for LLM reasoning.
*   Mitigated RDNA 4 / ROCm 7.1 stability issues through contiguous memory enforcement and illegal memory access patches.

### **The Fact Verification System**
*   Implemented a `pending_knowledge` buffer for unverified claims.
*   Launched a background thread that automatically performs web searches to verify technical facts extracted from conversation.

### **The Hardware Guardian**
*   Deployed a systemd-level watchdog (`buddy-guardian.service`) that monitors GPU thermals and Klipper printer states in real-time, providing a safety net for autonomous operations.

## 4. Future Roadmap: Phase 3 & 4
*   **Proactive Agency:** Moving from "Response-Only" to "Peer-Initiated" check-ins based on shop telemetry.
*   **Desktop Vision:** Integrating VLM (Vision Language Models) to allow the Buddy to "see" CAD failures or printer spaghetti in real-time.
*   **The Vault (RAG):** Indexing local engineering libraries for instant, offline specification retrieval.

---
**"From a tool to a peer."**
