---
name: sync-swarm-state-via-scratchpad
description: Synchronize files and state between distributed swarm nodes (Architect and Worker) using the SQLite Message Bus Scratchpad API. Use when a remote node needs to read/write files that reside on the Architect's filesystem but are not accessible via shared disk (Split-Brain).
---

## When to Use
Use this skill when an agent is running on a remote node (e.g., P100) and needs to access data, code, or logs that exist only on the Architect node (e.g., 9070 XT), or vice versa. This bypasses the "Split-Brain" filesystem limitation where `/mnt/TG_2TB` is not shared across the network.

## Procedure

### 1. Write Data to the Scratchpad (Sender)
If you have local data that a remote agent needs, push it to the Message Bus.

- **Option A: Using Tools**
  Use `starbuck_write_scratchpad(key, value)`.
- **Option B: Using Shell (Architect)**
  ```bash
  curl -X POST http://127.0.0.1:8000/scratchpad \
       -H "Content-Type: application/json" \
       -d '{"key": "unique_resource_name", "value": "PASTE_CONTENT_HERE"}'
  ```

### 2. Read Data from the Scratchpad (Receiver)
On the remote node, pull the data using the unique key.

- **Option A: Using Tools**
  Use `starbuck_read_scratchpad(key)`.
- **Option B: Using Shell (Remote Node)**
  ```bash
  # Ensure MESSAGE_BUS_API is set correctly (e.g., 10.0.0.5)
  curl -s http://10.0.0.5:8000/scratchpad/unique_resource_name
  ```

### 3. Verification
Confirm the data transfer was successful by checking the output of the read command or tool.

## Pitfalls and Fixes
- **Loopback Error:** If the remote node attempts to read from `127.0.0.1`, it will fail.
  - **Fix:** Always use the Architect's LAN IP (e.g., `10.0.0.5`) in the Message Bus URL on remote nodes.
- **Key Collisions:** Using generic keys like `test` or `data` can lead to overwriting other agents' work.
  - **Fix:** Use specific keys based on the task and timestamp (e.g., `task_f637ddad_config`).
- **Data Size:** The scratchpad is intended for text-based resources (code, logs, JSON). Large binary blobs should be avoided.

## Agentic State-Sync Protocol (Orchestrator Push)
This protocol solves the "Split-Brain" issue by forcing the Architect to actively negotiate distributed memory routing instead of masking it with mount points.

1. **Read Local File:** Use `file_read` to capture the content of the target file on the Coordinator node (e.g., 9070 XT).
2. **Push to Scratchpad:** Use `starbuck_write_scratchpad(key, content)`. 
   - **Constraint:** The Architect is strictly forbidden from embedding raw file strings inside the delegation prompt itself to prevent context window bloat.
3. **Delegate Task:** Use `delegate_task`. Pass the unique scratchpad key inside the `provided_resources` Zod schema array so the subagent knows where to fetch its data.
4. **Subagent Pull:** The subagent (on the remote P100 node) pulls the content using `starbuck_read_scratchpad(key)` as its first action to initialize its local environment.