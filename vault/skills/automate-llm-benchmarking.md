---
name: automate-llm-benchmarking
description: Procedure for automating objective LLM-as-a-Judge benchmarks across multiple hardware/software configurations. Use when you need to map VRAM boundaries, test quantization stability, or optimize llama-server launch arguments for ROCm/Nvidia hardware.
---

# Automate LLM Benchmarking

This skill provides a procedural framework for running autonomous, iterative benchmarks to find the "Goldilocks" configuration for local LLMs.

## The Scientific Method (Automation Loop)

To find optimal settings without manual testing, implement a master Python orchestrator (`the_scientist.py`) that follows this loop:

1.  **Define Configuration Grid**: Create a list of dictionaries containing different `HSA_ENABLE_SDMA` values, `-ub` (micro-batch) sizes, and TurboQuant `-ctk`/`-ctv` cache types.
2.  **Graceful Restart**: Kill any existing `llama-server` instances (`pkill -f llama-server`) and wait ~3 seconds for VRAM to clear.
3.  **Bootstrap Server**: Launch the server with the next configuration from the grid. Monitor stdout for the "HTTP server listening" signal.
4.  **Execute Trial**: Trigger the agentic test suite (e.g., `npx tsx examples/apollo_lab.ts`). This should record raw tool-calling traces and telemetry.
5.  **Trigger Judge**: Run the LLM-as-a-Judge script (e.g., `python3 lab/judge.py`) to grade the trial results using a stronger model (e.g., P100 node or cloud model).
6.  **Log Matrix**: Append the score, generation speed (TPS), and configuration name to a central `benchmarks.csv` file.

## Key Metrics to Track

-   **Adherence Score**: Did the model follow strict JSON schemas or enter a "2-Bit Drunk" loop?
-   **Tokens Per Second (TPS)**: Raw generation speed.
-   **Context Efficiency**: How many tokens did the model use to complete the task? (Higher precision quants often use fewer tokens than lower ones).
-   **VRAM Stability**: Did the trial crash with an Illegal Memory Access or OOM?

## Pitfalls & Verification

-   **VRAM Fragmentation**: On AMD hardware, multiple restarts can sometimes lead to VRAM creep. Monitor `rocm-smi` if benchmarks begin to fail unexpectedly.
-   **Greedy Collapsing**: If testing MoE models, ensure `temperature` is above 0.0 in the test suite to prevent `<think>` block collapse.
-   **Port Binding**: Ensure the script waits for the port to actually be free before attempting to restart the server.
