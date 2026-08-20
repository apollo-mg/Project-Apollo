# Apollo Swarm Operations & Runbook

This guide covers the boot sequence, crash recovery, and edge case handling for the distributed Apollo Sovereign Swarm, including our multi-node fleet and Kubernetes sandboxing.

## 🖥️ Fleet Topology (Final State)

The Swarm spans three primary physical nodes, connected via the local network and coordinated by the SQLite Message Bus:

1. **The Control Plane (Local - 10.0.0.5):** 
   - **Hardware:** AMD RX 9070 XT (16GB VRAM) / Ryzen 7 5700X3D
   - **Role:** Hosts the SQLite Message Bus (`data/message_bus.db`), the Glass Cockpit UI (`apollo_server.ts`), and the Antigravity CLI (`agy`). Acts as the semantic sanitizer and central hub. 
2. **The Codebase Investigator (Quad-P100 - 10.0.0.194):**
   - **Hardware:** 4x Nvidia Tesla P100 Server (64GB Total VRAM)
   - **Role:** Runs the `FastContext-1.0-4B-RL` model for instantaneous, parallelized `Glob`/`Grep` operations via GRPO tool calling.
3. **The Sovereign Orchestrator (SLI Node - 10.0.0.73):**
   - **Hardware:** 2x Nvidia Tesla P100 (32GB Total VRAM)
   - **Role:** Runs the `Darwin-36B-Opus-ABLITERATED` model via `llama-cpp-turboquant` (layer-splitting enabled). Handles extreme 64k+ context window tasks and deep reasoning loops.

---

## 🚀 Standard Boot Sequence

### 1. The Control Plane
To bring the centralized message bus and coordinator online safely, use the unified controller script. This handles PID locking, prevents duplicate ghost processes, and isolates execution.
```bash
cd /mnt/TG_2TB/Projects/Apollo
./apollo-ctl.sh start
```

You can check the health of the Control Plane at any time:
```bash
./apollo-ctl.sh status
```

To gracefully tear down the swarm (allows SQLite WAL flushing and clean task aborts):
```bash
./apollo-ctl.sh stop
```

### 2. The Worker Nodes
On remote execution nodes (e.g., the Quad-P100 or Dual-P100 SLI servers), start the worker daemon:
```bash
ssh mark@10.0.0.73
cd /mnt/HDD/Apollo
# Start the Python worker daemon
./venv_cachyos/bin/python3 worker_daemon.py &
```

### 2b. P100 GPU Power/Clock State (standing config since 2026-07-17)

Both P100 nodes (`.73` dual, `.194` quad) run a systemd oneshot unit
`/etc/systemd/system/p100-efficiency.service` at boot:
`nvidia-smi -pm 1; -pl 150; -ac 715,1063` — the efficiency point from the 2026-07-16
power/clock sweeps (+25% decode tok/J at 84% speed; the 150W cap costs −0.3% on
layer-split MoE decode). Receipts: `.73:~/power_sweep_results.txt`, `~/clock_sweep_results.txt`.

**Benchmark discipline: every benchmark receipt MUST record the GPU power/clock state it
ran under** (`nvidia-smi --query-gpu=power.limit,clocks.applications.graphics,clocks.applications.memory --format=csv`).
Numbers taken under this config are NOT comparable to boot-default (autoboost 1328 MHz)
numbers — including all receipts from before 2026-07-17 (carveout_panel, quant_ladder,
abv3–v7, puzzle_lab), which ran at boot defaults. To restore defaults for a
comparison run: `sudo nvidia-smi -rac && sudo nvidia-smi -pl 250` (revert:
`sudo systemctl restart p100-efficiency`).

### 3. The Interactive Terminal (Antigravity CLI)
With the transition to the new official Google interface, launch the interactive agent terminal natively from the project root:
```bash
agy
```
*Antigravity automatically reads `.antigravity.md` and `AGENTS.md` to map the Swarm's structure to its internal TUI.*

---

## ⚠️ Edge Cases & Fault Tolerance

**1. No Applicable Nodes for a Task**
If the Fleet Admiral (`CapabilityRouter`) evaluates the `fleet_status` table and finds 0 nodes matching a task's physics requirements:
*   **Synchronous Orchestrator Tasks:** The Router logs a warning and falls back to the default local model (e.g., Qwopus 27B on the 9070 XT).
*   **Asynchronous Sub-Agent Tasks (Message Bus):** The task is published to the SQLite queue with strict constraints. It remains `pending` until a capable node boots up.

**2. Worker Crashes Mid-Execution**
If a node claims a task but OOMs or loses power:
*   The `message_bus_api.py` runs a background `timeout_checker` thread.
*   Every 60 seconds, it sweeps the database. If a task has been `in_progress` for over 15 minutes without an update, it is forcibly reset to `pending` so another node can claim it.

**3. Network Partition (SSE Disconnect)**
If the TypeScript Orchestrator loses connection to the Python Message Bus while waiting for an SSE callback:
*   The `EventSource` protocol natively attempts to reconnect indefinitely.
*   We use a strict **30-minute safety timeout** in `delegate-task.ts`. If the SSE event never arrives, the Promise rejects, preventing the orchestrator from hanging forever, and logs a timeout failure.

**4. A2A Split-Brain State Sync Failures**
Because remote workers (like the SLI Node) do not share the physical disk of the Control Plane, they suffer from "Split-Brain" if an agent attempts to read a local file.
*   **Resolution:** Ensure agents use the `starbuck_write_scratchpad` MCP tool to push local file contents to the Message Bus database, passing only the `scratchpad_id` to the remote subagent. The remote node must use `starbuck_read_scratchpad` to retrieve the data before acting.

---

## 🛠️ Crash Recovery & Diagnostics

*   **Database Lockups:** If the Swarm stalls, manually inspect the SQLite queue (ensure you check `data/`, not `vault/`):
    `sqlite3 data/message_bus.db "SELECT * FROM task_queue;"`
*   **CUDA Static Assertion / Split-Mode Crashes on P100s:** If `llama-server` on the Dual-P100 node crashes with `ggml_backend_cuda_split_buffer_set_tensor`, ensure you are launching with `-fit off` to force layer-splitting instead of row-splitting on Pascal hardware.
*   **Zombie System Locks:** If package managers get stuck on a Starbuck worker, spawn a sub-agent with `YOLO LEVEL 3` clearance to run `starbuck_execute_fix` with `dpkg --configure -a` or manually remove `.lck` files.

---

## 🔬 Automated LLMOps (The Scientist)

To map new hardware boundaries or test a newly downloaded GGUF model, run **The Scientist**. This utility automatically profiles the model using `llama-bench`, launches it, subjects it to a "2-Bit Lobotomy" stress test, and updates the Capability Router's database.

```bash
cd /mnt/TG_2TB/Projects/Apollo
python3 modules/the_scientist.py --model /path/to/your/model.gguf --node RX_9070_XT
```
*Note: The Scientist aggressively claims VRAM during profiling. Do not run it while the node is actively serving Swarm tasks.*

---

## 🛡️ Project Starbuck Kubernetes Sandboxing

To securely execute untrusted sub-agent code, the Swarm uses a lightweight Kubernetes (K3s) cluster equipped with the `agent-sandbox` controller.

**How it works:**
*   **agent-sandbox:** Uses `runtimeClassName: gvisor` to provide a hard, VM-like boundary preventing container escapes.
*   **SandboxWarmPool:** K3s maintains a "Warm Pool" of pre-booted environments. When an agent requests a sandbox, one is allocated in milliseconds, preventing UI Reflex Arc stalling.

### The Consensus Crucible (Adversarial Detonation)
Tasks involving complex code execution employ the **Proposal-Consensus-Detonation Pattern**:
1. **Proposal**: A Software Engineer sub-agent generates code.
2. **Consensus**: A roster of Judge agents ruthlessly reviews the code. Vulnerabilities trigger a rewrite loop (up to 3 rounds).
3. **Detonation**: Once a strict quorum is reached, the verified code is tunneled to the Starbuck P100 daemon and safely executed inside a Warm Pool Kubernetes Sandbox.

**Deployment Instructions (P100 Node):**
1.  **Install K3s:** `curl -sfL https://get.k3s.io | sh -`
2.  **Install the agent-sandbox Controller:**
    ```bash
    kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.4.6/manifest.yaml
    kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v0.4.6/extensions.yaml
    ```
3.  **Apply the Swarm Manifests:**
    ```bash
    kubectl apply -f deploy/kubernetes/sandbox-template.yaml
    kubectl apply -f deploy/kubernetes/sandbox-warmpool.yaml
    ```