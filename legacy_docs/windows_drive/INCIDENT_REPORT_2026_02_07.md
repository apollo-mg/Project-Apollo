# Incident Report: Failed GPU STT Optimization
**Date:** February 7, 2026
**Subject:** Attempted migration of `faster-whisper` to ZLUDA (AMD GPU) on Windows 11.

## 1. Executive Summary
An attempt was made to optimize the "WidowMaker" voice engine by migrating speech-to-text (STT) processing from the CPU (Ryzen 5700X3D) to the GPU (AMD RX 9070 XT) using the ZLUDA translation layer. The effort resulted in a series of cascading library errors and system instability, ultimately failing due to kernel-level incompatibilities between `ctranslate2` and ZLUDA's cuDNN implementation on Windows. The system has been fully reverted to its original working CPU-only state.

## 2. Timeline of Events
*   **01:00:** Proposed [EXPERIMENTAL] GPU acceleration via ZLUDA to reduce transcription latency.
*   **01:15:** Verified hardware visibility (ZLUDA detected 1 GPU). Misinterpreted this as proof of functional compatibility.
*   **01:30:** Encountered `cublas64_12.dll` missing error. Attempted library aliasing and `ctranslate2` version downgrades.
*   **01:45:** Hit `CUDNN_STATUS_INTERNAL_ERROR`. Attempted side-loading cuDNN 8 libraries from DaVinci Resolve.
*   **02:00:** Encountered dependency chain failures (`FileNotFoundError` for `ctranslate2.dll`).
*   **02:15:** Attempted "Pure CUDA" fallback by disabling cuDNN via environment variables.
*   **02:30:** Voice engine became unstable, picking up background noise and failing to detect wake words due to over-engineered buffer logic.
*   **02:45:** User requested full reversion. Cleanup executed; all infrastructure changes, temporary environments, and DLL modifications were removed.

## 3. Root Cause Analysis
*   **Technical Failure:** While ZLUDA can bridge basic CUDA calls, it cannot currently translate the complex, proprietary deep-learning kernels in cuDNN 8/9 required by `ctranslate2` on Windows.
*   **Agentic Failure:** Failed to perform a "Research First" feasibility check. Relied on generalized knowledge of ZLUDA rather than searching for specific `faster-whisper` + ZLUDA success stories.
*   **Verification Failure:** Initial verification was limited to "is the GPU visible?" rather than "can the GPU perform a 1-second transcription?"

## 4. Remediation & New Guardrails
To prevent future "rabbit holes" and time-sinks, the following mandates have been added to `INFRASTRUCTURE_CONTEXT.md` and `TIERED_AI_STRATEGY.md`:
1.  **Mandatory Web Search:** Any task involving experimental bridges (ZLUDA/ROCm) or OS/Hardware mismatches (AMD + Windows ML) requires a verified community success story before planning.
2.  **Functional Payload Test:** Hardware verification must include a real-world functional test within the first 10 minutes.
3.  **Two-Error Rule:** If fixing Error A leads to a deeper Internal Error B, the agent must stop and provide a "Sunk-Cost Analysis" and a pivot to a stable path.
4.  **Stability Priority:** Stability and "Known Solved" patterns are now prioritized over theoretical optimization.

## 5. System Status
*   **Hardware:** 5700X3D (CPU) is the primary STT processor.
*   **Software:** Python 3.14 (System Default).
*   **Voice Engine:** `commander_voice.py` restored to original configuration (Whisper `base`, Threshold `200`).
*   **Result:** System is 100% stable and operational.
