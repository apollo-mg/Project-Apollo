---
name: integrate-mcp-tool-to-apollo-server
description: Workflow to integrate a new MCP (Model Context Protocol) tool into the Apollo TypeScript server. Use when a new Python system tool (The Hands) needs to be connected to the orchestrator (The Brain) and visualized in the Glass Cockpit UI (The Eyes).
---

# Integrate MCP Tool to Apollo Server

This skill provides a procedural guide for bridging a new Model Context Protocol (MCP) tool into the Apollo Sovereign architecture.

## Workflow

### 1. Define the Tool in the Daemon
Add the new tool to the relevant MCP daemon (e.g., `starbuck_daemon.py`). Ensure it uses the `@mcp.tool()` decorator and returns a structured response.

```python
@mcp.tool()
async def my_new_tool(arg1: str) -> str:
    """Description for the LLM."""
    # Implementation
    return "Result"
```

### 2. Connect the Daemon in the Orchestrator
In `apollo_server.ts`, ensure the daemon is connected via `connectMCPTools`. If it's a new daemon, add it to the `startServer` function.

```typescript
const myDaemonMCP = await connectMCPTools({
  command: '/path/to/venv/bin/python3',
  args: ['/path/to/daemon.py']
}, registry)
```

### 3. Expose to the UI (Optional)
If the tool provides data for the Glass Cockpit (e.g., a file tree or system status), emit a WebSocket event.

```typescript
// Inside the tool execution logic or a periodic update loop
ws.send(JSON.stringify({
  type: 'my_tool_update',
  data: result
}))
```

### 4. Update the Profile Configuration
Add the tool name to the `allowed_tools` array for the relevant agent profile in `profiles.yaml`.

```yaml
architect:
  allowed_tools:
    - ...
    - my_new_tool
```

## Failure Shields

- **The Ghost Profile Trap**: If a tool is defined in the daemon and connected in the server but not listed in `profiles.yaml` for the active agent, the agent will not be aware of it and will not call it.
- **Path Resolution**: MCP daemons often run in a different working directory. Use absolute paths for all file operations inside the daemon.
- **Venv Isolation**: Always use the absolute path to the virtual environment's Python binary (`.../.venv/bin/python3`) when spawning the daemon to avoid "ModuleNotFoundError".
