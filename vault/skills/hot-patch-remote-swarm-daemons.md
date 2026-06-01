---
name: hot-patch-remote-swarm-daemons
description: Procedurally hot-patch Docker-based worker daemons on remote nodes using docker exec to bypass image persistence issues. Use when minor logic fixes (like unused imports or path tweaks) need to be applied to remote nodes without triggering a full Docker image rebuild.
---

# Hot-Patching Remote Swarm Daemons

This skill provides a procedure for surgically updating application logic inside running Docker containers on remote hardware nodes (e.g., P100, Pi 5) when a full `docker build` is too slow or the remote environment configuration is unknown.

## Procedure

### 1. Identify the Target Container
SSH into the remote node and list active containers to find the daemon's exact name.
```bash
sudo docker ps
```
*Evidence from Apollo:* 9070 node uses `apollo-worker-daemon`, while the P100 node uses `apollo-worker-daemon-p100`. (Use the latter for the dedicated inference node).

### 2. Execute Surgical Edit
Use `docker exec` with `sed` to modify the file directly inside the container's filesystem.

**Example: Remove a specific line (e.g., a broken import)**
```bash
sudo docker exec [container_name] sed -i '/import yaml/d' /app/worker_daemon.py
```

**Example: Replace a string**
```bash
sudo docker exec [container_name] sed -i 's/old_string/new_string/g' /app/config.py
```

### 3. Restart the Daemon
Restart the container to force the Python/Node process to reload the modified script into memory.
```bash
sudo docker restart [container_name]
```

### 4. Verify the Patch
Check the container logs to ensure the daemon boots without the previous error.
```bash
sudo docker logs --tail 20 [container_name]
```

## Pitfalls & Gating
- **Volatile Changes:** Edits made via `docker exec` are **temporary** and will be lost if the image is rebuilt or the container is deleted and recreated. Always apply the same fix to the local source code and trigger a proper build when time allows.
- **Path Awareness:** The path inside the container (e.g., `/app/worker_daemon.py`) may differ from the host path. Verify the working directory inside the Dockerfile.
