# Apollo Sovereign Engine & Project Starbuck Roadmap

> **Mission:** Transition the Apollo Sovereign Engine from a brittle, manually synchronized set of scripts into a robust, containerized, and autonomous "Managed Cluster" supervised by the Apollo OS and deployed by Project Starbuck.

---

## Stage 1: The Managed Cluster Baseline (Containerization)
*The goal of this stage is to eliminate "Environment Drift" and standardize heterogeneous hardware execution (CUDA vs. ROCm) across the P100 and 9070 XT nodes.*

1. **Dockerize the Core:** Finalize and test the `Dockerfile.worker` image, pinning Node.js 22, Python 3, and the exact `open-multi-agent` TSX framework.
2. **Deploy the Central Nervous System:** Spin up the `message_bus_api.py` (FastAPI + SQLite WAL) as an independent, network-addressable Docker container.
3. **Stateless Worker Daemons:** Deploy the containerized `worker_daemon.py` on both the main PC (RX 9070 XT) and the remote server (P100).
4. **Hardware Validation:** Verify that the swarm successfully routes and executes tasks asynchronously without hanging prompts, missing schemas, or path hallucination errors.

---

## Stage 2: Decoupling the "Glass Cockpit"
*The goal is to separate the heavy, synchronous inference tier from the lightweight, responsive User Interface.*

1. **WebSocket Migration:** Rip out the existing REST/polling logic in `apollo_server.ts` and the `index.html` frontend.
2. **Persistent Bi-Directional Streams:** Implement real-time WebSockets to stream agent `stderr`, `stdout`, and internal `<think>` blocks seamlessly to the UI.
3. **Stateful UI:** Ensure the dashboard remains completely fluid and responsive even when the local 35B model is under extreme context pressure (e.g., processing a 260k token codebase chunk).
4. **Pause & Edit (The Kill Switch):** Expose an interrupt sequence over the WebSocket to halt runaway sub-agents, a prerequisite for the Starbuck Level 2 YOLO hierarchy.

---

## Stage 3: Operationalizing "The Scientist" (Automated LLMOps)
*The goal is to relieve the human operator of playing "VRAM Tetris" by automating server configuration and benchmarking.*

1. **Benchmarking Pipeline:** Formalize the objective, deterministic LLM-as-a-Judge test suite on the 9070 XT.
2. **Parameter Optimization:** Task the Scientist agent with dynamically testing various `llama-server` arguments (e.g., `-ub`, `-ctk q8_0`, `-ctv turbo4`) to map the edge of the VRAM boundary.
3. **The Knowledge Base:** Have the Scientist output a continuous matrix of known-good configurations for specific hardware targets (P100 vs. 9070 XT).
4. **Dynamic Scaling:** Wire the Scientist's output directly into the Capability Router, ensuring Apollo always dispatches tasks to optimally configured models.

---

## Stage 4: Project Starbuck (The Agentic Bootstrap)
*The ultimate goal: Apollo OS becomes capable of deploying itself.*

1. **MCP Server Daemon:** Build the Starbuck daemon using the Model Context Protocol (MCP) over WebSockets to handle real-time, interactive terminal streaming (critical for compiler errors).
2. **The YOLO Parameter:** Implement the 4-tiered permission hierarchy (Paranoid, Supervised, Trust but Verify, Full YOLO) within the Apollo OS control plane.
3. **Hardware Reconnaissance:** Grant Starbuck secure, supervised access to host-level commands (`lspci`, `nvidia-smi`, `rocm-smi`).
4. **Autonomous Deployment:** Test Starbuck's ability to drop onto a raw Linux node, analyze its VRAM, dynamically write a `docker-compose.yml` for the Apollo Swarm, and autonomously boot the cluster.
