# Apollo Sovereign Engine: Asynchronous Distributed Architecture Overview

This document provides a functional overview of the datacenter-grade, distributed AI orchestration layer built for the Apollo Sovereign Engine. By implementing this architecture, we have directly realized the **CapabilityRouter** and **MessageBus** paradigms inspired by the Anthropic KAIROS documents, allowing local-first, asynchronous delegation across a hardware swarm.

## 1. Core Architecture

### The Database (`message_bus.py`)
At the heart of the system is the SQLite database operating in **WAL (Write-Ahead Logging)** mode. This is a critical design choice that allows the writer (e.g., the RX 9070 XT node running the Sovereign Coordinator) and the reader (e.g., the P100 Node running the Daemon) to access the exact same queue simultaneously without throwing "Database Locked" errors.

### Hardware Physics (The Capability Router)
By defining "Hardware Physics" (e.g., `NODE_NAME`, `CONTEXT_WINDOW`, `PRECISION_BITS`), the entire hardware swarm is future-proofed. The system can gracefully scale from massive dual-P100 servers down to edge devices like a Raspberry Pi 5. If the Sovereign Coordinator requests a 32,768-token audit, the database natively routes the task away from a node with a 16GB VRAM limit and hands it straight to a capable 32GB node.

### The Worker Daemon (`worker_daemon.py`)
This script runs endlessly in the background on your hardware nodes. 
- **Endless Polling Loop:** The Daemon wakes up every 3 seconds to check the SQLite Message Bus for pending tasks that match its hardware constraints. Because of WAL mode, this polling never locks out the Sovereign Coordinator from writing new tasks.
- **Atomic Task Claiming:** When a task matches the Daemon's hardware physics, it uses an **EXCLUSIVE TRANSACTION** to instantly mark the task as `claimed` and tag it with its `NODE_NAME`. This completely solves the "Double Claim" bug, ensuring that multiple nodes don't accidentally start doing the same work, wasting compute cycles.
- **CPU Throttling:** Because the daemon runs in an endless loop on machines where system RAM needs to manage large VRAM payloads, it should be launched with the Linux `nice` command (e.g., `nice -n 15 python3 worker_daemon.py`). This lowers its CPU scheduling priority, ensuring that your host OS UI and background tasks remain responsive while the daemon silently crunches tasks.

### The Headless Bridge (`oma.js`)
Once a task is claimed, the Daemon pipes the task's payload directly into the standard input of the headless `oma.js` subagent runner. This perfectly bridges the Python daemon with the upstream `open-multi-agent` TypeScript framework. When execution finishes, the massive output payload is written back to the SQLite row and the status is marked as `completed`.

## 2. CLI Tooling

The Sovereign Coordinator interacts with this architecture via two primary TypeScript tools:

### `dispatch_task`
This tool drops tasks into the queue without freezing the terminal.
1. It defines the `task_name` and the `payload`.
2. It sets the **Capability Physics** constraints (e.g., `min_context: 32768`, `min_precision: 4.0`).
3. The tool instantly writes this to the SQLite database and immediately returns control to the CLI.

### `check_task`
A companion polling tool for the CLI. Whenever you want to retrieve the results of a dispatched task, the Sovereign Coordinator runs `check_task` with the given `task_id`. It reaches into the SQLite database and reads the output payload without blocking.

## 3. The Full Asynchronous Workflow

With this architecture, the async delegation loop operates seamlessly:

1. **User:** *"Hey Apollo, audit the entire codebase for security flaws."*
2. **Sovereign Coordinator:** Realizes this is a massive job. Uses the `dispatch_task` tool.
3. **Sovereign Coordinator:** Responds: *"Task dispatched! I'm ready for your next question."* (Zero terminal freeze).
4. **Worker Daemon:** Wakes up on the P100 node, sees the task, verifies it has the context window for it, and atomically claims the task. It starts grinding the subagent loop.
5. **User (later):** *"Hey Apollo, did the P100 finish that audit yet?"*
6. **Sovereign Coordinator:** Uses the `check_task` tool, grabs the results from the SQLite bus, and summarizes the security flaws.

## 4. Future Roadmap

As the swarm scales, the following paradigms will drive the next evolution of the Sovereign Engine:

### Dynamic Load Balancing (The Fleet Admiral)
The primary Sovereign Coordinator should not need to be hardcoded with knowledge of the network topology or specific endpoints. Instead, a specialized, highly quantized routing LLM (or robust algorithmic Capability Router) will oversee load balancing. The main agent simply requests an outcome (e.g., "I need a codebase audit"), and the Load Balancer dynamically assigns it to the most appropriate, available network asset based on real-time node physics (VRAM, context window, current load) and the task's mathematical requirements.

### Seamless Callbacks (Interrupt-Driven Architecture)
The user should never have to manually poll the agent (e.g., "Did the subagent finish yet?"). By implementing an **Interrupt-Driven Architecture** (such as a WebSocket bridge or a background thread in the CLI framework), the Worker Daemon can push a notification back to the primary Sovereign Coordinator the moment a task transitions to `completed`. The main agent can then gracefully interrupt the user's current session to announce: *"Your massive codebase audit just finished on the P100. Here are the critical security flaws I found..."* This creates a truly magical, asynchronous swarm experience.

## 3. Distributed State-Sync (Agent-to-Agent Handoff)

With the introduction of the Glass Cockpit UI and the multi-node distributed topology (e.g., 9070 XT Coordinator and P100 Worker), the Swarm faced a critical "Split-Brain" filesystem issue. When the Architect on Node A delegates a task to a subagent on Node B, the subagent cannot access the physical files on Node A's disk. 

Rather than masking this issue with an OS-level NFS mount, the Apollo Swarm implements a pure **Agent-to-Agent (A2A) State-Sync** mechanism using the SQLite Message Bus, forcing the models to actively negotiate distributed memory routing.

### The Agentic Scratchpad
The SQLite database contains a dedicated `scratchpad` table (equipped with REST endpoints) acting as centralized, transient swarm memory.

### The Orchestrator Push Protocol
The Sovereign Architect's Identity (`LOCAL_AGENT_CONTEXT.md`) explicitly forbids delegating tasks without verifying spatial awareness.
1. The Architect reads the local file using standard `file_read`.
2. It pushes the file contents over the network to the SQLite database via the FastMCP `starbuck_write_scratchpad` tool.
3. It hands off the task via `delegate_task`, passing the newly generated scratchpad key inside the `provided_resources` Zod schema array. The Architect is strictly forbidden from embedding the raw file string inside the prompt itself to prevent context window bloat.

### The Subagent Pull Protocol
When the remote daemon claims the task, it spins up the subagent (e.g., `software_engineer`).
1. The `apollo_cli.ts` boot sequence dynamically injects profile-specific `system_instructions` from `profiles.yaml`.
2. The subagent reads the prompt and sees it has `provided_resources`.
3. Following its strict mandates, it uses the `starbuck_read_scratchpad` FastMCP tool to pull the file data over the network from the SQLite database.
4. After processing, it writes the modified state back to the database via `starbuck_write_scratchpad` and reports the new key to the Architect.
