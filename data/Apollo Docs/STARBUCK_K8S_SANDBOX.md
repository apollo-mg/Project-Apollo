# Project Starbuck: Kubernetes Agent Sandbox Architecture

## Overview
This document serves as the architectural blueprint for upgrading Project Starbuck (the Execution Plane) from generic Docker containers to a secure, dynamically provisioned Kubernetes environment. The strategy is centered around the [`kubernetes-sigs/agent-sandbox`](https://github.com/kubernetes-sigs/agent-sandbox) Custom Resource Definition (CRD).

## The Motivation: Defusing the Docker Time Bomb
Running raw Python worker daemons (like `worker_daemon.py` on the P100) inside generic Docker containers presents a massive security vulnerability. Standard containers share the host kernel. If an untrusted AI workload hallucinates a destructive command, or falls victim to an indirect prompt injection via a downloaded repository, it could easily break out of the container or compromise the host environment. 

The Apollo Control Plane must be strictly decoupled from this risk.

## The Solution: `agent-sandbox`
The `agent-sandbox` is a Kubernetes controller specifically designed to manage **isolated, stateful, singleton workloads** for AI agent runtimes. It provides a lightweight, single-container VM experience.

### Key Architectural Pillars for Starbuck

#### 1. Strong Sandbox Isolation (gVisor & Kata Containers)
The Sandbox API goes beyond standard Docker namespaces. It supports robust, secure runtimes like **gVisor** or **Kata Containers**. This provides true kernel-level and network isolation. When the Sovereign Architect delegates a risky task to a Starbuck subagent, the code executes inside a hardened micro-VM that physically cannot access the host OS. This strictly enforces the YOLO permission hierarchy.

#### 2. The Stateful Singleton Advantage
Standard Kubernetes deployments are stateless and disposable. However, agentic workloads require long-running execution contexts and persistent memory. The `agent-sandbox` treats pods as **stateful singletons** with stable network identities and persistent storage attached.
- **Deep Hibernation & Auto-Resume:** The daemon can save its state to disk, hibernate to free up compute resources, and automatically wake back up on network connection with its workspace, files, and IP address perfectly intact.

#### 3. Killing the Cold Boot (SandboxWarmPool)
When the Apollo Control Plane delegates an immediate tool call to Starbuck, waiting 30 seconds for a fresh container image to pull and boot destroys the real-time interaction loop.
- **The Warm Pool Extension:** This controller manages a roster of pre-warmed sandboxes that can be instantly allocated to agents, completely eliminating cold-start latency. Tasks are assigned and executed in milliseconds.

## Next Steps for Integration
1. **Lightweight Kubernetes Deployment:** Investigate deploying a lightweight Kubernetes distribution (e.g., K3s, K0s, or MicroK8s) on the dedicated P100 worker node to act as the host for the Sandbox controller.
2. **Daemon Routing Logic:** Finalize the internal daemon routing and Message Bus state-sync protocol to ensure it can gracefully handle dispatching tasks to dynamically allocated IP addresses provided by the `agent-sandbox` service.
3. **Template Design:** Author the `SandboxTemplate` YAML manifests that define the baseline tools, environment variables, and memory volume mounts for Starbuck subagents.