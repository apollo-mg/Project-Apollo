---
name: implement-gpu-aware-idle-monitoring
description: Implementation of Exponentially Weighted Moving Average (EWMA) for GPU monitoring to allow background agents to yield to sustained load while ignoring transient spikes.
---

## When to Use
Use this skill when a background agent (e.g., a background researcher or epiphany generator like "Daydream Daemon") needs to monitor system load to avoid interrupting user-intensive tasks (e.g., gaming, 4K video buffering, or rendering). Simple utilization thresholds often fail due to transient spikes; EWMA provides a smoothed metric for more reliable yielding.

## Procedure
1.  **Poll GPU Utilization**: Create a background thread that periodically polls the GPU utilization (e.g., using `rocm-smi` on AMD hardware).
    -   Example command: `rocm-smi -u --json`
    -   Frequency: Every 2-5 seconds.
2.  **Calculate EWMA**:
    -   Initialize `gpu_ewma = 0.0`.
    -   Use a smoothing factor `alpha` (typically 0.2).
    -   Formula: `gpu_ewma = (alpha * current_usage) + ((1 - alpha) * gpu_ewma)`.
    -   **Note:** Use a `threading.Lock()` when reading/writing the `gpu_ewma` variable to ensure thread safety.
3.  **Implement Threshold Check**: In the agent's idle check function (e.g., `is_system_idle()`), compare the `gpu_ewma` against a predefined threshold (e.g., 15%).
4.  **Yield Logic**: If `gpu_ewma > threshold`, the agent should pause or skip its current task.

## Pitfalls and Fixes
-   **Symptom**: Agent pauses for brief video buffering spikes or OS UI glitches.
    -   **Cause**: `alpha` is too high (response is too fast).
    -   **Fix**: Lower `alpha` (e.g., to 0.1 or 0.05) to increase the time-window for smoothing.
-   **Symptom**: Agent doesn't yield fast enough to a newly launched game, causing initial stutter.
    -   **Cause**: `alpha` is too low (response is too slow) or polling frequency is too low.
    -   **Fix**: Increase `alpha` or increase the polling frequency (e.g., to 1 second).

## Verification
-   **Transient Test**: Run a high-load but brief task (e.g., buffering an HD video or refreshing a complex web page). The agent should NOT yield.
-   **Sustained Test**: Run a sustained high-load task (e.g., a game, 3D render, or heavy LLM inference). The agent SHOULD yield after a few seconds once the EWMA crosses the threshold.
-   **Log Check**: Monitor the daemon logs to see the `gpu_ewma` values and ensure they are trending correctly.
