---
name: maintain-rdna4-stability
description: Maintain long-term stability for LLM servers on AMD RDNA 4 (RX 9070 XT) by mitigating VRAM creep and fragmentation.
---

## When to Use
Use this skill when running local LLM servers (`llama-server`) for extended periods (20+ hours) on AMD RDNA 4 hardware, especially when experiencing VRAM "creep" or GUI stuttering.

## Procedure

### 1. Optimize `llama.cpp` Launch Arguments
Ensure the server uses the following flags for wavefront alignment and memory efficiency:
- `-ub 64`: Aligns micro-batches with AMD wavefronts (64 threads) and reduces peak VRAM pressure during prefill.
- `-ctk q8_0 -ctv turbo3` (or `tq4_1s` if using RotorQuant): Enables asymmetric TurboQuant caching to minimize KV cache footprint.
- `-c 65536`: Use a large context window only if stabilized by the above flags.

### 2. Implement a VRAM Watchdog
Create a background script (e.g., `vram_watchdog.py`) that monitors GPU telemetry and triggers a restart sequence when free memory is low.

**Watchdog Logic:**
1. **Monitor:** Query `rocm-smi --showmeminfo vram --json` every 5 minutes.
2. **Threshold:** If `vram_free < 400MB` (or a razor-thin margin), initiate restart.
3. **Pause:** Create a lock file (e.g., `daydream_pause.lock`) to signal background daemons to pause *before* their next task.
4. **Quiesce:** Wait (e.g., 30s) for active thoughts/generation to finish.
5. **Restart:** Kill the `llama-server` PID, wait for VRAM to flush (verify with `rocm-smi`), and restart via the standard launch script.
6. **Resume:** Remove the lock file to resume background tasks.

### 3. Environment Variables
Set these for ROCm stability:
```bash
export HSA_ENABLE_SDMA=1        # Use 1 if using TurboQuant/MoE Micro-batching; 0 for legacy stability.
export PYTORCH_TUNABLEOP_ENABLED=0 # Keep OFF to avoid kernel instability.
```

## Pitfalls and Fixes
- **Symptom:** Chrome GUI or OS desktop stutters every few seconds.
  - **Cause:** VRAM is 100% full; ROCm is frantically swapping fragmented memory to system RAM (GTT) over the PCIe bus.
  - **Fix:** Decrease the `VRAM_CRITICAL_FREE_MB` threshold in the watchdog or increase the frequency of checks.
- **Symptom:** FOMO (Fear Of Missing Out) or interrupted epiphanies.
  - **Cause:** Watchdog kills the server mid-thought.
  - **Fix:** Ensure the background daemon checks for the existence of `daydream_pause.lock` *between* tasks, and the watchdog waits long enough for the current task to finish.

## Verification
- Run `rocm-smi` and verify `VRAM Total Used` does not plateau at the card's maximum capacity for more than 5 minutes.
- Check `watchdog.log` for successful "Restart sequence complete" entries.
