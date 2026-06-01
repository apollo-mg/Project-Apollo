---
name: sync-starbuck-state-via-scratchpad
description: Procedure for synchronizing file contents or system state between a Starbuck worker and the Apollo Architect using the SQLite Message Bus Scratchpad API.
---

# sync-starbuck-state-via-scratchpad

Use this skill when a Starbuck worker node needs to pass reconnaissance data (logs, file contents, status reports) to the Lead Architect or other workers in the distributed swarm.

## Core Mechanism

Starbuck uses the SQLite Message Bus `/scratchpad` REST API. This allows nodes to share key-value pairs even if they do not share a filesystem.

## Procedure

### 1. Write Data (From Worker/Daemon)
Use the `starbuck_write_scratchpad` tool (or the internal `urllib` implementation in `starbuck_daemon.py`).

```python
# In starbuck_daemon.py
def push_reboot_log():
    log_content = read_reboot_log() # e.g., tail -n 100 /var/log/boot.log
    starbuck_write_scratchpad(key="p100_last_reboot_log", value=log_content)
```

### 2. Read Data (From Architect/Other Worker)
Use the `starbuck_read_scratchpad` tool.

```python
# The Architect detects a node just came online
status = starbuck_read_scratchpad(key="p100_last_reboot_log")
if status:
    # Process the log
    pass
```

## Best Practices

- **Unique Keys**: Namespace keys by node ID (e.g., `9070xt_apt_fail_log`) to prevent collisions in the global scratchpad.
- **Large Payloads**: Avoid pushing massive files (>1MB) to the scratchpad to prevent SQLite performance degradation. Truncate logs to the last 50-100 lines.
- **Verification**: After writing, the tool returns a success message confirming the key was updated.

## Verification Checklist
- [ ] Is the `MESSAGE_BUS_API` environment variable set?
- [ ] Does the key include a node identifier?
- [ ] Is the value a string? (Complex objects must be JSON-serialized).
