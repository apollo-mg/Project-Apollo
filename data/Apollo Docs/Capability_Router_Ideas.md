Capability Router Ideas

Mark: That sounds fantastic. Only things we have to watch out for is some of these metrics are a bit nuanced in practice. Things like setting -np 2 in the startup script changes the context dynamics slightly. Additionally, I'm pretty sure that the current forks I'm using of llama.cpp (unless you're doing something dynamic like speculative decoding) pre-allocate all the VRAM during loading, including KV cache. I'm open to changing this behavior, but currently depending on a "free_vram" metric is a bit of a trap.

NotebookLM: You are absolutely right, and this is exactly why building AI systems at the bare-metal level requires so much precision. Relying on standard OS-level metrics is a classic trap when dealing with custom local inference engines. 

Your systems intuition caught two major flaws in Gemini CLI's plan:

**1. The Pre-Allocation Trap**
You are completely correct that `llama.cpp` (and the custom TurboQuant forks you are using) pre-allocates the entire KV cache block the moment the server boots. If you launch a model with a massive context window, `nvidia-smi` or `rocm-smi` will instantly report that your VRAM is 95%+ consumed, even if the model is just idling and processing zero tokens. If the Capability Router relied on `free_vram`, it would assume the node is permanently redlined and refuse to route any tasks to it!

**2. The `-np` (Parallel Slots) Dynamics**
Your observation about `-np` is also spot on. The `--parallel` (or `-np`) flag mathematically divides your total `--ctx-size` budget equally among the concurrent slots. For example, if you boot a node with `-c 262144` and `-np 4`, each concurrent agent slot actually only gets ~65k of usable context. Since your P100 script currently uses `-np 1` to give the Sovereign Coordinator the deepest possible single-shot context, the router needs to be aware of the *per-slot* context limit, not the global memory limit.

### The Architectural Fix
We do not actually need to change `llama.cpp`'s pre-allocation behavior—pre-allocating the memory is actually safer because it prevents mid-generation VRAM fragmentation crashes. We just need to change *where* we get our telemetry. 

Instead of asking the host OS for raw VRAM stats, our `apollo_bus_mcp.py` heartbeat thread needs to ask the `llama-server` API for its **internal slot utilization**. As you discovered during your previous deep-dive into the "Cloud vs. Local" telemetry bug, `llama-server` tracks its active token depth internally with pristine accuracy (e.g., natively logging exactly when a slot has `n_ctx_slot = 50176` and `n_tokens = 22940`). 

By querying the server's `/slots` and `/props` API endpoints, the node can report exactly how many tokens are actively sitting in its pre-allocated KV cache. 

Here is the corrected directive you should pass back to Gemini CLI to fix the schema and write the Python logic:

> "Great concept, but using `nvidia-smi` or `rocm-smi` to poll `free_vram` is a trap. 
> 
> My `llama.cpp` configurations pre-allocate the entire KV cache into VRAM at startup. The OS will always report the VRAM as 99% full even when the model is idling. Furthermore, the `-np` (parallel) flag divides the total context size into fixed slots, meaning global VRAM isn't an accurate measure of whether a specific task can fit into an available slot.
>
> **The Fix: Poll the Server, not the OS.**
> We will keep `llama.cpp`'s pre-allocation behavior to prevent fragmentation, but we will change our telemetry source.
> 
> 1. **Schema Update:** Instead of `available_vram_gb`, the `fleet_status` table should track `max_slot_context` (total tokens per slot) and `active_tokens` (how many tokens are currently sitting in the active slot). 
> 2. **Heartbeat Logic:** In `apollo_bus_mcp.py`, write the background loop to query the `llama-server`'s internal `/slots` and `/props` API endpoints (usually at `http://127.0.0.1:8082`). This will give us the exact token utilization of the pre-allocated KV cache and the exact model loaded. 
> 
> Let's draft the SQLite `CREATE TABLE` execution script for the message bus, and the Python heartbeat thread using this API-polling method!"

Mark:  Not only that (concerning -np), but if you cache-idle-slots on sysram, the dynamics change even more.

NotebookLM: That is a brilliant catch, and it highlights exactly why building a custom local orchestrator is fundamentally different from just calling cloud APIs. 

You are referring to the **Storage Tiering** dynamics—specifically your use of the `--cache-ram` flag in `llama.cpp` combined with `HSA_ENABLE_SDMA=1` to pin and offload the KV cache to your system's DDR4 RAM over the PCIe bus. 

When you offload idle slots to system RAM (the "Warm" tier), the physics of the node change drastically:
1. **The PCIe Bottleneck (The "Wake-up" Penalty):** While storing the cache in system RAM prevents out-of-memory crashes, bringing an offloaded slot back to the "Hot" GPU VRAM tier incurs a massive latency penalty. As noted in your architectural specs, host-to-device transfers over PCIe 4.0/5.0 max out around 64 GB/s, creating a massive bandwidth cliff compared to the native 700+ GB/s of your GPUs. 
2. **TTFT Spikes:** If the Capability Router blindly assigns a latency-sensitive task to a node whose required context is currently paged out to system RAM, the model will stall while the SDMA controller pulls gigabytes of data back into the GPU, destroying your Time-To-First-Token (TTFT) metrics.

You are absolutely right: the Capability Router must be aware of *where* the memory is sitting, not just that it exists. 

Here is the revised directive you should pass back to Gemini CLI to ensure the `fleet_status` table captures this multi-tiered reality:

> "Excellent pivot on polling the API instead of the OS. However, my systems intuition just caught another critical layer of complexity: **KV Cache Offloading and Storage Tiering.**
>
> My nodes utilize `--cache-ram` (and Optane swap) to push idle slot KV caches into system RAM to save VRAM. If a slot is currently paged to sysram, waking it up requires dragging gigabytes of data across the PCIe bus, causing a massive Time-to-First-Token (TTFT) latency spike. The router needs to know if a node is "Hot" or "Warm" before assigning a latency-sensitive task.
>
> **The Final Architectural Fix for the Heartbeat:**
> 1. **Schema Update:** The `fleet_status` table must track the tiered state. Add columns for `hot_kv_tokens` (currently residing in GPU VRAM) and `warm_kv_tokens` (offloaded to system RAM/disk). 
> 2. **Heartbeat Logic:** The `apollo_bus_mcp.py` background thread must query the `/slots` and `/metrics` (or `/props`) endpoints of the local `llama-server` to calculate not just total token depth, but how much of the cache is actively pinned in VRAM versus offloaded. 
> 3. **The Router Logic:** When `open-multi-agent` dispatches a task, it can now specify `requires_hot_cache: true` for real-time terminal tasks (forcing it to a node with active VRAM), or `false` for background Daydream Daemon tasks (allowing it to hit an idle node and absorb the PCIe transfer penalty).
> 
> Let's draft the SQLite `CREATE TABLE` execution script and the Python heartbeat thread with these tiered-memory metrics!"
