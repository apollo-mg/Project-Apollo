---
name: deploy-remote-sovereign-worker
description: Procedure to provision and connect a remote hardware node (P100, Pi 5) to the Apollo Sovereign Swarm via the SQLite Message Bus API. Use when the user wants to expand the cluster or offload inference to a dedicated node.
---

# Deploy Remote Sovereign Worker

This skill provides a validated procedure for adding a new physical node to the Apollo Sovereign Swarm.

## Procedure

1. **Establish SSH Bridge**
   Ensure the local host can jump to the remote node without a password prompt.
   ```bash
   ssh-copy-id <user>@<remote-ip>
   ```
   Verify with `ssh -o BatchMode=yes <user>@<remote-ip> 'echo success'`.

2. **Verify Remote Environment**
   Check for the Apollo repository and the `worker_daemon.py` script.
   ```bash
   ssh <user>@<remote-ip> 'ls -la Projects/Apollo/worker_daemon.py'
   ```

3. **Identify Local Bus IP**
   Determine the IP address of the primary desktop (the one hosting `message_bus_api.py`).
   ```bash
   ip -4 addr show # Look for the 10.0.0.x address
   ```

4. **Launch the Worker Daemon**
   Start the daemon in the background using `nohup`. You MUST provide the `MESSAGE_BUS_API` pointing to the desktop and define node-specific "Hardware Physics".
   ```bash
   ssh <user>@<remote-ip> 'nohup bash -c "MESSAGE_BUS_API=http://<desktop-ip>:8000 NODE_NAME=<name> NODE_ROLE=<architect|executor> CONTEXT_WINDOW=32768 PRECISION_BITS=16.0 /usr/bin/python3 Projects/Apollo/worker_daemon.py" > Projects/Apollo/worker_daemon.log 2>&1 &'
   ```

5. **Verify Connection**
   Check the remote log file for the "Listening for tasks" confirmation.
   ```bash
   ssh <user>@<remote-ip> 'tail -n 10 Projects/Apollo/worker_daemon.log'
   ```

## Failure Shields (Environment Drift)

- **Missing Modules**: If the log shows `ModuleNotFoundError: No module named 'yaml'`, ensure the global Python environment or specific venv has `pyyaml` and `fastmcp` installed.
- **Path Mismatches**: Workers often attempt to use absolute paths (e.g., `/mnt/TG_2TB/...`) found in tasks. If the remote node does not have the exact same mount points, file operations will fail.
- **Sudo Constraints**: Remote subagents cannot use `sudo` for local edits if the shell is non-interactive. Prefer manual edits via the primary agent over remote subagent delegation for system-level files.
- **Centralized Config**: Remote workers automatically fetch `profiles.yaml` from the desktop's `/config/profiles` endpoint. Only edit the master file on the desktop.
