---
name: harden-distributed-message-bus
description: Procedural maintenance for the SQLite-backed distributed Message Bus. Use when encountering "Database Locked" errors, stale lock files, or remote environment initialization failures (e.g., venv/ensurepip).
---

## When to Use
Use this skill when the Apollo swarm becomes unresponsive, the Message Bus API hangs, or remote worker daemons fail to boot due to missing Python dependencies.

## Procedure

### 1. Clear Stale SQLite Locks
If the Message Bus API or `message_bus_api.py` hangs or throws persistent `database is locked` errors (despite WAL mode):
1. Navigate to the project data directory: `/mnt/TG_2TB/Projects/Apollo/data/`.
2. Locate the `db.lck` file (or `message_bus.db-shm` / `message_bus.db-wal` if cleanup failed).
3. Delete the stale `.lck` file manually.
4. Restart the `message_bus_api.py` process.

### 2. Fix Remote Environment Initialization
If a `worker_daemon.py` on a remote node (e.g., P100) fails to create a virtual environment with errors like `No module named 'ensurepip'` or `python3.14-venv` not found:
1. SSH into the remote node (`mark@10.0.0.71`).
2. Run: `sudo apt update && sudo apt install python3.x-venv` (replace `x` with the target version, e.g., `3.14`).
3. Re-run the `worker_daemon.py`.

### 3. Verify Connectivity
Test the bus from the remote node using `curl`:
```bash
curl http://10.0.0.5:8000/heartbeat
```
If it returns `{"status": "ok"}`, the node is successfully reaching the Coordinator.

## Pitfalls
- **Loopback Drift:** Remote nodes often default to `127.0.0.1:8000` for the Message Bus. This will fail.
  - **Fix:** Ensure the remote node's environment variable `MESSAGE_BUS_API` is explicitly set to the Coordinator's LAN IP (`10.0.0.5`).
- **Permissions:** Stale lock files created by a different user or a root process (e.g., Docker) might require `sudo rm` to clear.
