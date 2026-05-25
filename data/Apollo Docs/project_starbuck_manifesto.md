# Project Starbuck: The Sovereign Sysadmin & Agentic Bootstrap

> **"Local first, cloud optional. ALWAYS."**

## 1. Executive Summary
**Project Starbuck** is an autonomous, agentic package manager and sysadmin daemon built for Linux bare-metal and distributed compute clusters. It serves as the vanguard worker-agent for the broader Apollo OS ecosystem. 

Where traditional package managers rely on brittle bash scripts and user intervention to resolve dependency conflicts, Starbuck dynamically reads raw compiler errors (`stdout`/`stderr`), patches kernel headers, fetches proprietary drivers (ROCm, CUDA), and forces installations through autonomously via the Model Context Protocol (MCP).

## 2. Core Architecture
Starbuck operates as an MCP Server daemon running in the background of the host OS. 
* **Connection Layer:** Utilizes WebSockets to maintain bidirectional, real-time streams during long-running compiler tasks or heavy sysadmin operations.
* **Communication Paradigm:** Agents communicate intent and reasoning via natural language (Markdown) to maximize cognitive headroom, but execute state changes strictly through deterministic MCP tool calls.
* **Sovereign Execution:** Capable of running locally on highly quantized models (e.g., 8B parameters) or scaling out to frontier API fallbacks (e.g., DeepSeek V4 Pro) when heavy reasoning is required.

## 3. The Agentic Hierarchy (Apollo OS Integration)
Starbuck is a highly privileged YOLO tool capable of root-level modifications. To ensure host stability, Starbuck is designed to operate under the supervision of **Apollo OS**, acting as the overarching Control Plane.

### The YOLO Parameter
Deployment risk is strictly controlled via a user-configurable parameter to dictate the level of autonomy:

* **Level 0 (Paranoid):** Strict Human-in-the-Loop (HITL). Starbuck pauses execution and requires manual user approval for all host-level commands.
* **Level 1 (Supervised):** Apollo OS acts as the discriminator. Starbuck generates an execution plan and passes it to Apollo. Execution is blocked until Apollo issues a deterministic `grant_execution_approval` tool call.
* **Level 2 (Trust but Verify):** Starbuck executes autonomously while streaming `stderr` directly to Apollo in real-time. Apollo maintains an active kill-switch to halt the thread if a catastrophic cascade is detected (e.g., overwriting a critical network bridge).
* **Level 3 (Full YOLO):** Starbuck runs completely unchained. User assumes all risks.

## 4. Phase 2: The Agentic Bootstrap (Apollo Unfolding)
Starbuck’s ultimate utility is serving as the automated bootstrap mechanism for deploying Apollo OS across heterogeneous homelab environments. 

Instead of requiring users to manually write cross-node Docker compose files, Starbuck will autonomously unfold the Apollo ecosystem:
1. **Hardware Reconnaissance:** Starbuck drops into the host environment and uses `lspci`, `nmap`, and `nvidia-smi`/`rocm-smi` to map the local network and available VRAM across available nodes (e.g., fast AMD triage nodes + legacy Nvidia datacenter worker nodes).
2. **Infrastructure Generation:** Dynamically writes the `docker-compose.yml` stack tailored to the discovered hardware constraints.
3. **Swarm Orchestration:** Provisions the Redis message bus, maps persistent volumes, establishes the WebUI, and pulls the containerized subagents.
4. **Handoff:** Once the network bridges are stable and the swarm is online, Starbuck transfers command authority to the newly booted Apollo OS control plane and reverts to a background sysadmin daemon.
