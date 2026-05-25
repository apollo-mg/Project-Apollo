# Skill Forge & Resource Allocation Architecture
## The "Bandwidth as a Service" Paradigm

**Core Concept:** 
Do not replicate the Linux scheduler. Let the Linux kernel handle the raw microsecond CPU slicing and page-faulting. Instead, the Sovereign Engine manages **Macro-Resource Allocation**—treating hardware (VRAM, Network, Disk I/O, LLM Compute) as tiered assets.

### 1. The Asset Tiers
*   **Tier 0 (Instant / Native):** Zoey (35B) logic, cached Python skills, local NVMe reads.
*   **Tier 1 (High Bandwidth / Local Compute):** Sonic (9B) code generation, Vision model inferences, local network scans.
*   **Tier 2 (High Latency / External):** Web scraping, API calls, pulling large repos.

### 2. Zoey: The Arbiter of Truth & Allocation
Zoey does not write the code. She is the Systems Architect. 
When intent is received, she performs a "Rapid Planning" assessment:
1.  **Is this a known skill?** -> Execute Tier 0.
2.  **Is this a new skill?** -> Allocate Tier 1 compute (Sonic).
3.  **Do we have the VRAM?** -> Check system state (already injected in her prompt). If VRAM is capped, she must decide: "Do I unload myself to let Sonic run, or do I queue this task?"

### 3. The Execution Loop (The Forge)
If a new skill is needed:
*   **Zoey:** "I need to forge a skill for this. Allocating compute to Sonic. Mark, this will take about 20 seconds." (User awareness).
*   **Sonic:** Generates the raw Python/C code.
*   **Execution:** The engine runs the code in an isolated subprocess (`subprocess.run`).
*   **Audit (The Arbiter):** 
    *   *Success:* Zoey hashes the intent, saves the script to `/skills/`, and reports success.
    *   *Failure:* Zoey reads the `stderr` traceback. She assesses: "Is this a logic error or a missing dependency?" She sends the traceback back to Sonic with specific correction instructions.

### 4. What we leave to Linux
*   Process scheduling (CFS).
*   Virtual memory paging (Swap/ZRAM).
*   Hardware interrupt handling.
*   File system journaling.

We only manage the *AI workflow* bandwidth, not the silicon bandwidth.