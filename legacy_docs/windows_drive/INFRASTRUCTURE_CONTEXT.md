# INFRASTRUCTURE CONTEXT: The Agentic Core
**Role:** System Architect & AI Infrastructure Engineer
**Focus:** Orchestrating Local AI, Voice Interfaces, and Hardware Asset Control
**Last Updated:** Feb 14, 2026

This document defines the "Compute & Command Center." This Gemini instance manages the infrastructure that enables all other specialized agents (like the Printer Assistant).

## 1. Host System Profile (Primary Compute Node)
*   **Operating System:** Linux (Ubuntu 22.04) / Windows 11 Pro (Dual Boot).
*   **CPU:** **AMD Ryzen 7 5700X3D** (8-Core with 3D V-Cache).
*   **RAM:** **32GB DDR4-3600mts**.
*   **GPU (Primary):** **AMD Radeon RX 9070 XT (16GB VRAM)**.
    *   *Architecture:* GFX1201 (RDNA 4).
    *   *ROCm Status:* **7.1.1 (Native Support)**.
    *   *PyTorch:* 2.9.1+rocm7.1.1.
*   **Audio I/O:**
    *   *Input:* System Default Mic (via `pvrecorder`).
    *   *Output:* System Default Speakers (via `aplay` / `sounddevice`).
*   **Development Stack:** Python 3.12, Bash.

## 2. Connected Project Assets
### Asset 01: The "Vz-Hybrid" (Ender 6 Conversion)
*   **Control Node:** Raspberry Pi 4 (10.0.0.83).
*   **Firmware:** Klipper.
*   **Connection:** Networked via Moonraker API.

## 3. The AI Infrastructure (Current Tools)
*   **Model Server:** ComfyUI (Port 8189) - Optimized for RDNA 4.
*   **Script Library:**
    *   `commander_voice.py`: Hands-free Command & Control (STT: Whisper, TTS: Kokoro).
    *   `generate_image.py`: Voice-to-Flux image generation pipeline.
    *   `vram_management.py`: Dynamic VRAM unloading utility (Critical for 16GB limit).
    *   `local_agent.py`: LLM interface for command processing.

## 4. Operational Protocols
*   **Dynamic VRAM Protocol:** Always trigger `unload_comfy_vram()` before and after heavy GPU tasks (Flux/Wan 2.1) to prevent "HIP Illegal Memory Access" or OOM.
*   **RDNA 4 Stability Mode:** 
    *   Use **Math Attention** (SDPA with `enable_math=True`) for reliability.
    *   Disable **SDMA** (`HSA_ENABLE_SDMA=0`) if PCIe instability occurs.
    *   Force **Contiguous** tensors for all Host-to-Device transfers.

## 5. Engineering Guardrails
*   **AMD/ROCm Priority:** Avoid `torch.compile` or Triton-based Flash Attention on RDNA 4 unless specifically patched for GFX1201.
*   **No Mixed Precision:** RDNA 4 `linear` kernels currently crash on mixed precision (FP32/FP16) in certain math operations. Force matching dtypes.

## 6. Future Infrastructure Roadmap
*   **Voice-to-CAD Engine:** Use local agents to generate OpenSCAD/STL assets via voice description.
*   **Swarm Routing:** Automatically swap local models in LM Studio based on task complexity (e.g., swapping DeepSeek for Llama 3).
*   **Visual Watchdog:** Integrate camera-based failure detection into the "Commander" voice feedback loop.