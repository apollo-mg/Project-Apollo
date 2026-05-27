# Project Starbuck: Kubernetes Agent Sandbox Architecture

## Overview
This document outlines the strategy for integrating the [`kubernetes-sigs/agent-sandbox`](https://github.com/kubernetes-sigs/agent-sandbox) Custom Resource Definition (CRD) into Project Starbuck.

## The Architecture: Bare-Metal Daemon + Disposable Sandboxes
The execution plane requires a bifurcated approach to security and capabilities. We cannot trap the primary execution daemon in a micro-VM, as it requires host-level access to manage the system. Instead, the architecture is defined by two distinct layers:

### 1. The Bare-Metal Starbuck Daemon (The Supervisor)
`starbuck_daemon.py` and `worker_daemon.py` will run natively on bare metal (or within a trusted, privileged environment).
- **Role:** Acts as the system administrator and task orchestrator for the execution node.
- **Permissions:** Operates under the YOLO 0-3 permission hierarchy, allowing it to manage the host OS, orchestrate Docker/Kubernetes, and interface with the SQLite Message Bus.
- **Function:** Receives tasks from the Apollo Control Plane and provisions resources.

### 2. The Kubernetes Agent Sandbox (The Disposable Workbench)
The `agent-sandbox` controller will be deployed to provide secure, ephemeral execution environments. This is specifically utilized as a **tool** for sub-agents (like the `software_engineer`).
- **Role:** A secure, disposable workbench for executing and testing untrusted, LLM-generated code.
- **Strong Isolation (gVisor & Kata Containers):** When the `software_engineer` needs to compile a random C++ fork, install unknown pip packages, or run a generated Python script, it executes inside this hardened micro-VM. It physically cannot escape into the host OS, protecting the bare-metal daemon.
- **The Stateful Singleton Advantage:** Sandboxes provide a stable network identity and persistent storage during a specific task's lifecycle. They can hibernate to save resources and auto-resume without losing state.
- **Killing the Cold Boot (SandboxWarmPool):** To maintain real-time interaction loops, the controller maintains a pool of pre-warmed sandboxes. When the `software_engineer` requests an execution environment, a sandbox is allocated in milliseconds.

## The Workflow
1. The **Sovereign Architect** delegates a coding task to the `software_engineer` sub-agent via the Message Bus.
2. The bare-metal **Worker Daemon** receives the task and spins up the sub-agent.
3. The `software_engineer` writes code and uses a custom tool (e.g., `execute_in_sandbox`) to run the code.
4. The tool instantly claims a pre-warmed `agent-sandbox` instance, pushes the code, executes it securely within the gVisor/Kata container, and returns the stdout/stderr.
5. If the code is destructive, the sandbox is simply destroyed, and the host remains perfectly safe.

## Next Steps for Integration
1. **Lightweight Kubernetes Deployment:** Deploy a lightweight Kubernetes distribution (e.g., K3s, K0s, or MicroK8s) on the dedicated P100 worker node to host the Sandbox controller.
2. **Tool Implementation:** Develop the `execute_in_sandbox` MCP tool for the Starbuck daemon, allowing sub-agents to claim and interface with the SandboxWarmPool.
3. **Template Design:** Author the `SandboxTemplate` YAML manifests defining the baseline runtimes (Node.js, Python, Rust) available in the warm pool.