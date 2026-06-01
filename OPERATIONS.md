# Apollo Swarm Operations & Runbook

This guide covers the boot sequence, crash recovery, and edge case handling for the distributed Apollo Sovereign Swarm.

## 🚀 Standard Boot Sequence

To bring the entire swarm online after a reboot:

1. **Start the Sovereign Message Bus (The Broker)**
   This is the central nervous system. It hosts the SQLite database and Server-Sent Events (SSE) stream.
   ```bash
   cd /mnt/TG_2TB/Projects/Apollo
   # Start the FastAPI server (we recommend running this in a screen/tmux session or as a systemd service)
   uvicorn message_bus_api:app --host 0.0.0.0 --port 8000
   ```

2. **Start the Hardware Beacons (Capability Physics)**
   On *every* physical node you want in the swarm (e.g., the 9070 XT desktop, the P100 server), run the MCP bridge. This script transmits their VRAM availability, precision, and OS status to the Fleet Admiral.
   ```bash
   # Make sure your Python venv is active
   python3 apollo_bus_mcp.py
   ```

3. **Start the Execution Daemons (The Hands)**
   Start the worker agents that will actually execute the tasks. For example, on the P100 server, start NullClaw:
   ```bash
   nullclaw agent
   ```
   *(Ensure NullClaw's `~/.nullclaw/config.json` has the Starbuck and Apollo Bus MCP tools registered).*

4. **Start the Orchestrator (The Brain)**
   Finally, launch the TypeScript CLI or UI Server on your primary workstation.
   ```bash
   cd engines/open-multi-agent-upstream
   # For the terminal CLI:
   npx tsx examples/apollo_cli.ts
   
   # For the WebUI Glass Cockpit:
   npx tsx examples/apollo_server.ts
   ```
   *The Fleet Admiral Capability Router will instantly query the database, find the nodes transmitting heartbeats, and route sub-agent tasks dynamically.*

---

## ⚠️ Edge Cases & Fault Tolerance

**1. No Applicable Nodes for a Task**
If the Fleet Admiral (`CapabilityRouter`) evaluates the `fleet_status` table and finds 0 nodes matching a task's physics requirements (e.g., all nodes are offline, or a task demands 120k context but only 32k nodes are active):
*   **Synchronous Orchestrator Tasks:** The Router logs a warning and falls back to the default `OPENAI_BASE_URL` defined in `profiles.yaml` (typically `127.0.0.1:8082`), effectively forcing the local machine to handle it.
*   **Asynchronous Sub-Agent Tasks (Message Bus):** The task is published to the SQLite queue with its strict requirements. It will sit in a `pending` state until a capable node boots up. 

**2. Worker Crashes Mid-Execution**
If a node claims a task but OOMs or loses power before completing it:
*   The `message_bus_api.py` runs a background `timeout_checker` thread.
*   Every 60 seconds, it sweeps the database. If a task has been `in_progress` for more than 15 minutes without an update, it is forcibly reset back to `pending` so another node can claim it.

**3. Network Partition (SSE Disconnect)**
If the TypeScript Orchestrator loses connection to the Python Message Bus while waiting for an SSE callback:
*   The `EventSource` protocol natively attempts to reconnect indefinitely.
*   We implemented a strict **30-minute safety timeout** in `delegate-task.ts`. If the SSE event never arrives, the Promise rejects, preventing the orchestrator from hanging forever, and logs a timeout failure back into the LLM's context so it can decide how to proceed.

## 🛠️ Crash Recovery

*   **Database Lockups:** If the Swarm completely stalls and tasks aren't routing, you can manually inspect the SQLite queue:
    `sqlite3 vault/message_bus.db "SELECT * FROM task_queue;"`
*   **Zombie System Locks:** If package managers (apt/pacman) get stuck on the Starbuck worker, spawn a sub-agent with `YOLO LEVEL 3` clearance to run `starbuck_execute_fix` with `dpkg --configure -a` or remove the pacman `.lck` file.

---

## 🔬 Automated LLMOps (The Scientist)

To map new hardware boundaries or test a newly downloaded GGUF model, run **The Scientist**. This utility will automatically profile the model using `llama-bench`, launch it via `llama-server`, subject it to a deep-context "2-Bit Lobotomy" stress test, and update the Capability Router's database with the verified physics.

```bash
cd /mnt/TG_2TB/Projects/Apollo
# Make sure your Python venv is active
python3 modules/the_scientist.py --model /path/to/your/model.gguf --node RX_9070_XT
```
*Note: The Scientist aggressively claims VRAM during its profiling phase. Do not run it while the node is actively serving live Swarm tasks.*