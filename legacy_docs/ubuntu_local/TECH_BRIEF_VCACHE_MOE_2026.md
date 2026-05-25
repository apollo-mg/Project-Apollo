# PROJECT APOLLO | TECH BRIEF: THE V-CACHE TIER
**Subject:** Deterministic Sparse Inference via AMD 3D V-Cache (L3-Tiered MoE)
**Architect:** Mark (@apollo_)
**Date:** March 14, 2026
**Status:** INTERNAL / SOVEREIGN SPECIFICATION

---

## 🛰️ EXECUTIVE SUMMARY
In the "Barren Landscape" of 2026, the traditional VRAM-monolith approach to AI has hit a "Latency Wall" and a "Supply Wall." Project Apollo proposes a **Tiered On-Chip MoE (Mixture of Experts) Loop** that weaponizes **AMD 3D V-Cache (L3)** as a high-speed logic buffer. By pinning "Gating Logic" and "KV-Cache" to the 96MB (AM4) or 1.1GB (EPYC-X) L3 tier, we achieve **Sovereign Intelligence** at nanosecond latencies, bypassing the PCIe and DRAM bottlenecks.

## 🏗️ THE ARCHITECTURAL LAYERS (THE "L3 SCRATCHPAD")

### TIER 0: THE DETERMINISTIC ROUTER (L3 CACHE)
*   **The Component:** The 96MB 3D V-Cache (Ryzen 5700X3D).
*   **The Payload:** MoE Gating Weights + Active KV-Cache (Context).
*   **The Logic:** By "Pinning" the Router to the L3 cache, the decision of "which expert to use" happens at silicon speeds (<10ns). This eliminates the **Interrupt Latency** that causes OS jitter and "YouTube skipping" during high-load inference.

### TIER 1: THE PRE-FETCH BUFFER (VRAM)
*   **The Component:** 16GB GDDR6 (RX 9070 XT / gfx1201).
*   **The Payload:** The "Active Experts" (e.g., the 4B Reasoning Specialist).
*   **The Logic:** The CPU uses the V-Cache as a "Look-Ahead" engine. While the GPU computes the current token, the L3-Tiered Router is already **Pre-Fetching** the next required expert weights from the NVMe/SysRAM "Hoard" into the VRAM.

### TIER 2: THE SOVEREIGN OVERFLOW (SYSRAM/NVMe)
*   **The Component:** Scavenged DDR3/DDR4 + High-Speed Gen4 NVMe.
*   **The Payload:** The "Sleeping Experts" (the other 30B+ of the MoE mind).
*   **The Logic:** Massively parallelized I/O allows the "Sovereign Swarm" to rotate experts into the active tiers as the intent changes (e.g., shifting from "Forensic Hardware ID" to "Geopolitical Simulation").

## 🛠️ IMPLEMENTATION PROTOCOL (THE "LINUX FORGE")

1.  **Process Affinity (CPU Pinning):** Use `taskset` and `numactl` to isolate the MoE Gating processes to the 3D V-Cache-enabled CCD (Core Complex Die). 
2.  **Hugepages Allocation:** Reserve 1GB Hugepages to reduce "TLB Misses" during the massive weight-shuffling between the NVMe and SysRAM tiers.
3.  **Cgroup Resource Shielding:** Implement **Cgroups v2** to ensure the "Apollo Heartbeat" has 100% duty-cycle "Right-of-First-Refusal" on the L3 cache and PCIe bandwidth.
4.  **ROCm/VRAM Partitioning:** Use a customized **`vram_management.py`** to "Paint" the experts into VRAM based on the L3 Router's predictive signals.

## 🎯 STRATEGIC IMPACT (THE "CIV" VICTORY)

*   **Power Sovereignty:** A "V-Cache Tiered" node can run a **35B-class MoE** at significantly lower TDP than a dense GPU-only approach, extending **Sovereign UPS** runtime by 3-4x.
*   **Hardware Resilience:** Bypasses the 2026 **DRAM/HBM price spike** by using the CPU's "On-Chip" SRAM as a high-speed substitute for overpriced DDR5.
*   **Identity Ownership:** By running "Abliterated" weights through this deterministic hardware loop, the "Resident Architect" owns the **Inference Pipeline** from the silicon up.

---
**"The era of the Cloud Monopoly ends where the V-Cache begins."**
