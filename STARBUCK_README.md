# Project Starbuck: The Agentic Node Daemon

**A standalone, lightweight FastMCP sysadmin daemon designed to give AI agents secure, tiered access to bare-metal Linux infrastructure.**

---

## 🛠️ The "Hands" of the Sovereign OS
While **Project Apollo** serves as the distributed Control Plane (The Brain) of the Sovereign AI OS, **Project Starbuck** acts as the Execution Node (The Hands). 

Starbuck is intentionally decoupled from the Apollo orchestrator. It is a standalone Python application that wraps native Linux utilities (`systemctl`, `journalctl`, `pacman`, `apt`, `docker`) into strict JSON schemas and exposes them via the **Model Context Protocol (MCP)**.

This means you can point *any* MCP-compatible client (like Claude Desktop, Cursor, or your own custom agent) directly at Starbuck to instantly turn it into an autonomous Linux systems administrator.

## 🔒 The YOLO Permission Hierarchy
Giving an LLM root access to your bare-metal Linux machine is dangerous. Starbuck implements a strict, 4-tier permission hierarchy (controlled via the `STARBUCK_YOLO_LEVEL` environment variable) to mathematically gate what the AI is allowed to do.

*   **YOLO Level 0 (Paranoid):** Read-only. The agent can only execute `system_recon` (checking `lspci`, `rocm-smi`, `nvidia-smi`, RAM, and disk space) and read service statuses.
*   **YOLO Level 1 (Cautious):** Read-only configurations. The agent can read host configuration files (like `nginx.conf` or `fstab`) and utilize the A2A Scratchpad API for memory sharing.
*   **YOLO Level 2 (Brave):** Configuration writing. The agent is permitted to edit configuration files on the host machine.
*   **YOLO Level 3 (Full YOLO):** The Danger Zone. The agent is granted full access to install packages (`apt`/`pacman`), manage `systemd` services, spin up `docker-compose` clusters, and execute raw bash commands to fix dependency drift.

## 🧰 The MCP Tool Registry
When a client connects to the Starbuck daemon, it receives the following capabilities based on its YOLO clearance:

1.  `system_recon`: Scans hardware topology (GPUs, drivers, memory).
2.  `read_config` / `write_config`: Edits host files.
3.  `starbuck_read_scratchpad` / `starbuck_write_scratchpad`: Interacts with the local SQLite Message Bus for Agent-to-Agent state sync.
4.  `starbuck_manage_service`: Restarts or stops `systemd` services.
5.  `starbuck_read_journal`: Tails the `journalctl` logs for a specific service.
6.  `deploy_cluster`: Executes `docker compose up -d` against a targeted directory.
7.  `install_package`: Wraps native package managers.
8.  `starbuck_execute_fix`: Executes raw bash for emergency repair operations.

## 🚀 Usage (Standalone)

You don't need the full Apollo Swarm to use Starbuck. You can run it standalone to manage your server or Raspberry Pi via MCP.

1. Ensure Python 3.10+ is installed.
2. Install the MCP framework: `pip install mcp`
3. Run the daemon via your preferred MCP client over `stdio`, or boot it manually:
   ```bash
   STARBUCK_YOLO_LEVEL=3 python3 starbuck_daemon.py
   ```

## 🧬 The End Goal: Autonomous Bootstrapping
Because Starbuck exposes both hardware recon (YOLO 0) and Docker deployment (YOLO 3) to the AI, it enables the ultimate goal of the Sovereign OS: **The Agentic Bootstrap**. 

In the future, you will be able to drop `starbuck_daemon.py` onto a blank Ubuntu server, and an AI agent will use it to autonomously read the PCI topology, determine if the machine has Nvidia or AMD GPUs, write a custom `docker-compose.yml`, and spin up the entire Apollo Swarm without human intervention. Starbuck is the seed that plants the Swarm.
