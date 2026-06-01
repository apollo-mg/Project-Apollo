---
name: implement-programmatic-tool-calling-ptc
description: Implement a Hermes-style Remote Procedure Call (RPC) system to execute complex Python scripts that call native host tools. Use when an agent needs to collapse a multi-turn, high-volume tool chain into a single context-saving turn.
---

# Implement Programmatic Tool Calling (PTC)

## Overview

Programmatic Tool Calling (PTC) collapses multi-step reasoning loops (e.g., searching, iterating over matches, reading files) into a single LLM turn. The LLM writes a Python script that uses a pre-injected `apollo_tool` library to communicate with an ephemeral Node.js RPC server on the host.

## Implementation Procedure

### 1. Create the PTC Tool (`src/tool/built-in/python-ptc.ts`)
Implement a tool that spins up a temporary HTTP server and executes the LLM's Python code.

```typescript
// Key components of the tool implementation:
// 1. http.createServer() to listen on a random port.
// 2. Map incoming POST /execute_tool payloads to ToolExecutor.execute().
// 3. Inject a Python stub that uses urllib to hit the localhost server.
```

### 2. The Python RPC Stub
Prepend this stub to the LLM's code before execution:

```python
import urllib.request, json, os

def apollo_tool(name, **kwargs):
    rpc_url = os.environ.get("APOLLO_RPC_URL")
    req = urllib.request.Request(f"{rpc_url}/execute_tool", json.dumps({"name": name, "input": kwargs}).encode())
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode())

# Native function aliases
def grep(pattern, path=None): return apollo_tool("grep", pattern=pattern, path=path)
def file_read(path, start_line=None, end_line=None): return apollo_tool("file_read", path=path, start_line=start_line, end_line=end_line)
```

### 3. Register the Tool
Add `pythonPtcTool` to the `BUILT_IN_TOOLS` array in `src/tool/built-in/index.ts` and export it.

## Prompting & Return Shapes

Models must be explicitly warned about the return shape of RPC tools to avoid parsing errors.

**Required Tool Description:**
> Programmatic Tool Calling (PTC): Write and execute a Python script that calls Apollo tools via local RPC. ONLY the final printed stdout is returned.
> **IMPORTANT: All tools return a dictionary `{"data": Any, "isError": bool}`.**
> **Note: For `grep` and `file_read`, `res["data"]` is a single string block, NOT a list.** Use `.splitlines()` to iterate.

## Pitfalls & Error Handling

- **Leading Whitespace:** Ensure the Node server trims user input before checking for slash commands if using a WebUI.
- **Port Collisions:** Use a random or ephemeral port for the Node.js HTTP server.
- **Cleanup:** Always kill the Node server and delete temporary Python files after the script exits.
