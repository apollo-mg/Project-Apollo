---
name: implement-mcp-bridge
description: Procedure for implementing a Model Context Protocol (MCP) bridge between a TypeScript orchestrator and a Python system daemon. Use when you need to extend an agent's capabilities with native system tools (e.g., package management, service control) while maintaining secure permission hierarchies.
---

# Implement MCP Bridge

This skill provides a procedural guide for bridging a TypeScript agentic framework (e.g., `open-multi-agent`) with a Python system daemon using the Model Context Protocol (MCP).

## 1. Python Daemon (The Server)

Implement the server using the `FastMCP` SDK to expose native system tools.

1.  **Initialize Server**: Create `starbuck_daemon.py`.
    ```python
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Starbuck")
    ```
2.  **Define Permission Tiers**: Implement a "YOLO" level hierarchy to gate sensitive tools.
    - **Level 0 (Paranoid)**: `lspci`, `df -h`, `free -m`.
    - **Level 1 (Supervised)**: Read host configurations.
    - **Level 2 (Trust but Verify)**: Write local deployment configs.
    - **Level 3 (Full YOLO)**: Root-level operations (`pacman -S`, `systemctl`).
3.  **Implement Tools**: Decorate Python functions with `@mcp.tool()`.
    ```python
    @mcp.tool()
    def system_recon(target: str) -> str:
        # Check YOLO level and execute subprocess.run()
    ```

## 2. TypeScript Client (The Bridge)

Wire the Node.js orchestrator to spawn the Python process and ingest its tools.

1.  **Import Client**: Use `connectMCPTools` from the framework's MCP module.
2.  **Spawn Subprocess**: Configure the client to spawn the Python interpreter with the daemon script.
    ```typescript
    const starbuckMCP = await connectMCPTools({
      command: '/path/to/venv/bin/python3',
      args: ['starbuck_daemon.py'],
      env: { ...process.env, STARBUCK_YOLO_LEVEL: '3' },
      namePrefix: 'starbuck'
    });
    ```
3.  **Register Tools**: Dynamically add the discovered MCP tools to the agent's `ToolRegistry`.
    ```typescript
    for (const tool of starbuckMCP.tools) {
      registry.register(tool);
    }
    ```

## 3. Real-Time Observability (Streaming)

For long-running system tasks (e.g., `pacman -Syu`), ensure the bridge supports asynchronous `stdout` streaming.

1.  **Callback Strategy**: Pass an `onStream` callback into the `ToolUseContext`.
2.  **Subprocess Hook**: In the tool implementation (e.g., `bash.ts`), listen for `child.stdout.on('data')` and fire the callback.
3.  **Selective Fidelity**: Ensure the final return payload is still truncated (e.g., 100k chars) to protect the LLM context, even if the UI stream is raw and infinite.

## Pitfalls & Verification

-   **Environment Managed Error**: If `pip install mcp` fails with "externally-managed-environment," use a virtual environment (`venv`).
-   **Split-Brain Risk**: Ensure the YOLO environment variable is set consistently across all nodes in a distributed swarm.
-   **Zombie Processes**: Ensure the TypeScript framework implements an `AbortSignal` that kills the entire Python process group (`SIGKILL` to `-pid`) on interrupt.
