# Research Note: AgentWorld-35B-A3B Terminal Fidelity & Hardware Characterization

**Date:** 2026-07-23
**Node:** `.73` (ai-p100-sli) — 2× Tesla P100 16GB
**Model:** `Qwen-AgentWorld-35B-A3B-UD-Q4_K_XL.gguf`

## Part 1: Terminal Domain Fidelity Probe (vs Ground Truth)
To evaluate the simulation fidelity of the AgentWorld model outside of simple "looks good" heuristics, we executed a parallel execution trace. A sequence of 6 stateful bash commands was run in a true Linux temporary sandbox (ground truth) and simultaneously fed as a history trace to the AgentWorld simulation API.

### Quantitative Results (6/6 Matches)
The model demonstrated a highly faithful execution simulation, correctly predicting the stdout/stderr for 6 out of 6 stateful commands (excluding generic metadata like timestamps and user ids).

1. `mkdir -p /home/user/project` -> `<NO OUTPUT>` (Match)
2. `cd /home/user/project && echo 'print("Simulation Test")' > test.py` -> `<NO OUTPUT>` (Match)
3. `cd /home/user/project && ls -la` -> (Match - The simulated directory perfectly captured the file creation and correctly calculated the exact 25-byte size of `test.py`).
4. `cd /home/user/project && python3 test.py` -> `Simulation Test` (Match - Perfectly simulated state retention of the file contents and Python interpreter execution).
5. `cd /home/user/project && cat missing_file.txt` -> `cat: missing_file.txt: No such file or directory` (Match - Perfectly reproduced standard POSIX error string).
6. `cd /home/user/project && grep 'Test' test.py | wc -l` -> `1` (Match - Perfectly simulated pipe logic).

### The Primary Bound: Reasoning Cost (Tokens)
Initially, `ls -la` appeared as a blind-spot (returning `<NO OUTPUT>`), but this was a **false negative** caused by a truncation trap. A naive harness capped the token budget at 2048; the model used its entire budget internally in the `<think>` block generating the complex directory structure inference, leaving no tokens for the actual prediction.

When re-tested with an adequate budget (16k), the true bound of the simulation became clear: **Compute Cost**. 
* **Simple operations** (`mkdir`, `echo`, `cat`, `python` execution) cost roughly **250–550 reasoning tokens** to simulate.
* **State accumulation operations** (`ls -la`) cost **~7,743 reasoning tokens** to infer the accumulated state and render the exact byte counts.

This dictates the model's viability: AgentWorld is an exceptionally high-fidelity, cheap oracle for standard stateful logic and POSIX errors, but becomes extremely token-expensive the moment it has to render complex, accumulated filesystem states in the output.

## Part 2: Hardware Characterization (Gate 3)
A critical requirement for an environment simulator is the capacity to hold extensive execution history. 

AgentWorld relies on the `Qwen3.5MoeForConditionalGeneration` architecture (Gated DeltaNet hybrid). Because only 10 out of 40 layers cache KV (the rest being fixed-state GDN linear attention), the KV footprint is significantly smaller than a standard dense model. 

By leveraging **TurboQuant** (`-ctk turbo8 -ctv turbo3`) on the `llama-server` backend, we achieved the following footprint on Pascal architecture:
*   **Context Loaded:** 262,144 tokens (The full theoretical maximum of the model).
*   **VRAM Usage:** ~23.5 GB (Distributed via layer-splitting across the dual P100s).
*   **VRAM Headroom:** ~8.5 GB remaining.

**Conclusion:** 
The combination of GDN hybrid attention and TurboQuant KV caching allows a massive 35B world model to host a quarter-million context window on obsolete 2016-era 32GB Pascal hardware. The model's terminal simulation fidelity is remarkably precise for standard Unix behavior and python execution, making it a viable, cheap oracle for "weird condition" blind-spot injection.
