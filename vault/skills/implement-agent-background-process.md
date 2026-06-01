---
name: implement-agent-background-process
description: Implement and maintain the `background_process` tool for the open-multi-agent framework. Use when agents need to spawn long-running shell commands (like dev servers) with PID tracking, log tailing, and automatic cleanup on exit.
---

# Implementing Background Process Orchestration for Agents

This skill describes the architectural pattern for implementing a background process tool in the `open-multi-agent` framework. This is essential for agents performing "Software Engineer" tasks that require starting servers or long-running tests without blocking the main agent loop.

## Architectural Pattern

A robust background process tool requires three core components: a process registry, log file management, and lifecycle hooks.

### 1. Process Registry
Maintain a `Map` of active PIDs to track state across agent turns.

```typescript
interface ProcessState {
  pid: number
  command: string
  child: ChildProcess
  stdoutPath: string
  stderrPath: string
}

const processes = new Map<number, ProcessState>()
```

### 2. Log Management
Redirect `stdout` and `stderr` to temporary files. This prevents memory leaks in the Node.js process and allows the agent to "read" logs on demand without bloating the context window.

```typescript
const stdoutPath = path.join(os.tmpdir(), `bg-out-${pid}.log`)
const outStream = fs.createWriteStream(stdoutPath)
child.stdout?.pipe(outStream)
```

### 3. Lifecycle Hooks (Zombie Prevention)
Register a process exit hook to ensure all spawned background processes are killed when the CLI or Orchestrator exits.

```typescript
process.on('exit', () => {
  for (const [pid, state] of processes) {
    process.kill(-state.pid, 'SIGKILL') // Kill process group
  }
})
```

## Tool Implementation (Zod Schema)

The tool should expose an `action` enum to allow granular control.

```typescript
inputSchema: z.object({
  action: z.enum(['start', 'stop', 'read', 'list']),
  command: z.string().optional(), // Required for 'start'
  pid: z.number().optional(),     // Required for 'stop' and 'read'
  lines: z.number().default(100), // Number of log lines to tail
})
```

## Workflows

### Starting a Process
- Use `child_process.spawn` with `{ detached: true, stdio: 'pipe' }`.
- Return the `pid` and log paths to the agent immediately.

### Reading Logs
- Use `tail` or manual file offsets to read only the *last* few lines of the log.
- **Never** return more than 100-200 lines to prevent context window overflow.

### Stopping a Process
- Use `process.kill(-pid, 'SIGTERM')`. The negative PID targets the entire process group, ensuring spawned workers (like Node.js sub-processes) are also killed.

## Pitfalls & Verification

- **PID Collisions**: In long-running systems, verify the PID is still active in the registry before attempting to read logs.
- **VRAM Overlap**: If the background process uses the GPU (e.g., a second inference server), it will likely cause an OOM for the main agent. Add a warning to the tool description.
- **Zombie Processes**: Verify cleanup by checking `ps aux | grep <command>` after closing the CLI.
