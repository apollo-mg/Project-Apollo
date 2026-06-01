---
name: harden-swarm-telemetry-and-timeouts
description: Procedures to fix Node.js block-buffering in Python daemons, implement SSE keep-alives, and reliably kill process groups for distributed LLM swarm orchestration.
---

# Harden Swarm Telemetry and Timeouts

This skill provides procedural fixes for common "silent hangs" and telemetry delays in distributed LLM swarms (Apollo Sovereign Engine).

## 1. Fix Node.js Block-Buffering in Python Daemons

### Problem
When a Python daemon (like `worker_daemon.py`) executes a Node.js CLI (like `apollo_cli.ts`) via a standard pipe (`stdout=PIPE`), Node.js detects it is not in a terminal and switches to **block buffering** (8KB). Logs (like `<think>` blocks) will not appear in the WebUI until the buffer is full or the process exits.

### Procedure
Use Python's `pty` module to allocate a pseudo-terminal, tricking Node.js into line-buffering mode.

```python
import pty
import subprocess
import os

master_fd, slave_fd = pty.openpty()

process = subprocess.Popen(
    cmd,
    stdout=slave_fd,
    stderr=slave_fd,
    text=False, # Use bytes for raw PTY capture
    cwd=engine_dir,
    env={**os.environ, "FORCE_COLOR": "1"} # Preserve ANSI colors
)
os.close(slave_fd) # Critical: close slave in parent
```

## 2. Linux PTY EOF Handling

### Problem
When reading from a PTY master file descriptor, Linux raises `OSError: [Errno 5] Input/output error` instead of returning an empty string (EOF) when the child process closes the terminal.

### Procedure
Wrap the reading loop in a `try...except` block:

```python
import errno

with os.fdopen(master_fd, 'r', encoding='utf-8', errors='replace') as stdout:
    while True:
        try:
            line = stdout.readline()
        except OSError as e:
            if e.errno == errno.EIO: # [Errno 5] Input/output error
                break # Treat as clean EOF
            raise
        if not line: break
        # Process line...
```

## 3. SSE Delimiters and Keep-Alives

### Problem
Server-Sent Events (SSE) clients (like Node's `eventsource`) will buffer infinitely or time out if data frames are malformed or the server is silent.

### Procedure
1. **Frame Termination**: Every SSE data frame MUST end with two literal newlines (`\n\n`). Do not use double-escaped `\\n\\n`.
2. **Immediate Welcome**: Send a `[System] Connected` message the moment a client connects to prevent initial timeouts.
3. **Keep-Alives**: Yield a `: keepalive\n\n` comment every 15 seconds if the message queue is empty.

## 4. Reliably Killing Process Groups in Node.js

### Problem
`child.kill('SIGKILL')` only kills the immediate shell wrapper. Grandchild processes (like a global `find` or `grep`) are orphaned, adopted by `init`, and keep the pipe open, freezing the LLM orchestrator loop.

### Procedure
Spawn the process in its own group and kill the group using a negative PID.

```typescript
// In the tool implementation (e.g. bash.ts)
const child = spawn('bash', ['-c', command], {
  detached: true, // Create a new process group
  stdio: ['ignore', 'pipe', 'pipe'],
});

// To kill on timeout/abort:
if (child.pid) {
  try {
    process.kill(-child.pid, 'SIGKILL'); // Note the minus sign
  } catch (e) {
    // Handle or ignore ESRCH
  }
}
```