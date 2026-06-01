---
name: implement-starbuck-mcp-tool
description: Procedure for implementing a new strictly-typed FastMCP tool in the Starbuck daemon, including sandboxing, YOLO gating, and semantic naming.
---

# implement-starbuck-mcp-tool

Use this skill when developing new system-level capabilities for the Project Starbuck daemon (`starbuck_daemon.py`).

## Core Principles

1.  **Safety First**: Strictly follow the YOLO gating hierarchy.
2.  **Strict Sandboxing**: All file/path-based tools MUST enforce boundaries.
3.  **Semantic Naming**: Name tools according to their mutation level to enable UI badging.
4.  **No Stdout Corruption**: Background threads or tools must NOT print to `stdout` to avoid corrupting the FastMCP JSON-RPC stream.

## Procedure

### 1. Define the Tool Specification
Classify the tool into one of these categories:
- **Read-Only**: Reconnaissance only (e.g., `starbuck_read_config`). Prefix: `starbuck_read_` or `starbuck_check_`.
- **YOLO Level 2**: Structured, whitelisted mutation (e.g., `starbuck_restart_service`). Prefix: `starbuck_manage_`.
- **YOLO Level 3**: Arbitrary bash execution (Highest risk). Prefix: `starbuck_execute_`.

### 2. Implement Sandboxing
For any tool accepting a path or directory argument:
```python
ROOT_WORKSPACE_DIR = os.path.abspath("/mnt/TG_2TB/Projects/Starbuck") # Or use os.environ.get("APOLLO_ROOT")

def validate_path(requested_path: str) -> str:
    resolved = os.path.abspath(os.path.join(ROOT_WORKSPACE_DIR, requested_path))
    if not resolved.startswith(ROOT_WORKSPACE_DIR):
        raise ValueError(f"Escape detected: {requested_path}")
    return resolved
```

### 3. Add to `starbuck_daemon.py`
Use the `@mcp.tool()` decorator. Provide a verbose docstring with the YOLO level.

```python
@mcp.tool()
def starbuck_my_new_tool(param: str) -> str:
    """
    [YOLO LEVEL X] <Description>
    """
    try:
        # Implementation using subprocess.run
        # Use capture_output=True, text=True, timeout=30
        pass
    except Exception as e:
        return f"Error: {str(e)}"
```

### 4. Background Telemetry (Optional)
If implementing a background task (like a heartbeat), ensure it runs in a `threading.Thread(daemon=True)` and uses a strict `try/except: pass` block.

## Pitfalls & Verification

- **Terminal Pager**: When using tools like `journalctl` or `git`, always use `--no-pager` to prevent the subprocess from hanging.
- **Sudo Integration**: Wrappers should automatically inject `sudo` for Level 2/3 tasks rather than requiring the LLM to provide it.
- **Verification**: Test the tool's schema by running `python starbuck_daemon.py` and checking for startup errors.
