---
name: configure-sovereign-swarm
description: Procedural setup and troubleshooting for the distributed Apollo Sovereign Message Bus architecture across multiple nodes (P100 Architect and 9070 XT Executor).
---

# Configure Sovereign Swarm

Use this skill to configure, debug, or extend the distributed multi-agent swarm architecture.

## Swarm Topology

1. **API Server (Port 8000)**: Primary SQLite database wrapper.
2. **Local Inference (Port 8082)**: Native `llama-server` on each node.
3. **Worker Daemons**: Polling clients that claim and execute tasks.

## Setup Procedure

### 1. Start the Message Bus API (9070 XT)
The API must run on the node with physical access to the `message_bus.db` file.
```bash
cd /mnt/TG_2TB/Projects/Apollo
# Ensure venv is active
python3 message_bus_api.py
```

### 2. Start Worker Daemons
Each node (local or remote) runs a daemon to claim tasks based on its "physics" (role/context).

**On Executor (9070 XT):**
```bash
export NODE_ROLE="sprint_executor"
python3 worker_daemon.py
```

**On Architect (P100):**
```bash
export MESSAGE_BUS_API="http://<9070_XT_IP>:8000"
export NODE_ROLE="lead_architect"
python3 worker_daemon.py
```

### 3. Launch the Web UI (P100)
Run the Node.js server from the local SSD clone to avoid network mount latency.
```bash
cd ~/Projects/Apollo/engines/open-multi-agent-upstream
export MESSAGE_BUS_API="http://<9070_XT_IP>:8000"
export LLM_ENDPOINT="http://127.0.0.1:8082/v1"
npx tsx examples/apollo_server.ts
```

## Critical Troubleshooting

### fetch failed (Firewall)
- **Symptom**: Remote nodes fail to POST tasks or logs to the API.
- **Fix**: Open ports 8000 and 8082 on the 9070 XT.
```bash
sudo ufw allow 8000/tcp
sudo ufw allow 8082/tcp
```

### Empty Telemetry Pane (Ad-blocker)
- **Symptom**: UI loads but the Swarm Telemetry pane remains empty despite successful log POSTs in the API terminal.
- **Fix**: Disable ad-blockers (ABP/uBlock) or ensure endpoints do not use keywords like "telemetry" or "tracking". (Use `/swarm/stream` instead).

### NPX Hang (Interactive Prompt)
- **Symptom**: Daemon claims task but stalls silently. `ps` shows `npx` waiting.
- **Fix**: Ensure `worker_daemon.py` uses `cwd` pointing to the directory with `node_modules` and include the `--yes` flag.
```bash
npx --yes tsx examples/apollo_cli.ts ...
```

### MTP Draft OOM
- **Symptom**: `llama-server` crashes with `cudaMalloc failed` during MTP initialization.
- **Fix**: Clamp physical batch size to reduce compute buffer footprint.
```bash
./llama-server ... -b 128 -ub 128 --spec-type draft-mtp
```
