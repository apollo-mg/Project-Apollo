---
name: manage-distributed-swarm-drift
description: Procedural methods to prevent and resolve "Environment Drift" in distributed multi-node LLM swarms (e.g., Coordinator/Worker setups). Use when deploying new worker nodes, updating core schemas, or encountering hung processes caused by interactive prompts or mismatched logic across nodes.
---

# Managing Distributed Swarm Drift

Distributed multi-node swarms are prone to "Environment Drift," where worker nodes fall out of sync with the lead coordinator, leading to silent failures, hung processes, and mismatched tool execution logic.

## 1. Diagnosis (The "Ghost" Failure)
Symptoms of environment drift include:
- Worker claims a task but uses 0% CPU/GPU.
- Sub-agents fail with schema validation errors (e.g., Zod/Pydantic errors).
- "Missing command" or "Interactive prompt" errors in remote logs.
- **"Split-Brain" Config**: A worker node claims a task but uses outdated model endpoints or missing tools because its local `profiles.yaml` is out of sync.

**Verification Steps:**
1.  SSH into the suspected node.
2.  Check for hung background processes: `ps aux | grep tsx` or `ps aux | grep node`.
3.  Inspect the process group to see if it's waiting on stdin.

## 2. Prevention Protocols

### Non-Interactive Tool Execution
When spawning tools from background daemons, always use non-interactive/auto-confirm flags to prevent the process from hanging on a `(y/n)` prompt.
- **npx/npm**: Always use `npx --yes <package>` or `npm install --yes`.
- **apt-get**: Always use `apt-get install -y`.

### The Centralized Config API (Anti-Desync)
Instead of manually syncing files like `profiles.yaml` or `LOCAL_AGENT_CONTEXT.md` across nodes (which causes "Split-Brain" desync), expose these configurations via a REST API on the lead coordinator's Message Bus.

1.  **Expose Config Endpoints**: Add `/config/profiles` and `/config/context` routes to your FastAPI message bus.
2.  **Mount Source Files**: Volume-mount the master `profiles.yaml` into the message bus container (read-only) so it can serve the live state.
3.  **Fetch on Boot**: Refactor orchestrators and sub-agents to `fetch()` their profiles and system prompts from `process.env.MESSAGE_BUS_API` during initialization.

## 3. The Immutable Solution: Containerization
To permanently eliminate drift, transition to a containerized "Managed Cluster" strategy.

1.  **Build Immutable Images**: Use a `Dockerfile` to bundle the exact versions of Node.js, Python, and the orchestration framework.
    - *Example Base*: `node:22-bullseye-slim` (pins the runtime).
2.  **Docker Compose Orchestration**: Use a centralized `docker-compose.yml` to deploy the entire stack.
    - This guarantees that "Node A" and "Node B" are bit-perfect clones.

## 4. Sandbox Awareness
Remember that tools like `docker` and `docker compose` are typically **not accessible** from within the Gemini CLI sandbox (`bwrap`).
- **Workaround**: Deployments and container builds must be triggered from the host terminal, not from within the agent's shell tool.
- **Starbuck Protocol**: Starbuck agents run as native host daemons (Level 3 YOLO) to bypass this isolation via an MCP bridge.
