---
name: manage-gemini-cli-sandbox
description: Detect and work around the Gemini CLI tool sandbox (bwrap) isolation to access host processes and GPU hardware.
---

## When to Use
Use this skill when an agent experiences "split-brain" system errors while executing shell commands or tools from within the Gemini CLI.

### Symptoms
- `killall` or `pkill` fail even though the process is visibly running in a host terminal.
- `ls /dev/kfd` or `ls /dev/dri/*` return "No such file or directory" despite ROCm being correctly installed.
- LLM servers (like `llama-server`) fail to bind to `localhost` ports that appear open.
- Multimodal (vision) models quietly fall back to CPU because they cannot "see" the GPU device nodes.

## Procedure

### 1. Verify Sandbox Presence
Run a shell command to check for the presence of the ROCm kernel fusion driver or direct rendering nodes.
```bash
ls /dev/kfd /dev/dri/renderD128
```
If this returns "No such file or directory" while the host has an AMD GPU, the sandbox is active.

### 2. Check Process Visibility
Attempt to list all running processes. In a `bwrap` sandbox, you will typically only see your own process and `ps` might show a very limited list.
```bash
ps aux | grep llama-server
```
If you cannot see the server you know is running, you are sandboxed.

### 3. Ask for Intervention
Since the sandbox is a client-side security feature (usually using `bwrap`), the agent cannot "escape" it autonomously. You must explicitly inform the user.
- **Action:** State that you are being isolated by the Gemini CLI Tool Sandbox.
- **Request:** Ask the user to disable "Gemini CLI Tool Sandboxing" in their settings or provide the necessary device/network permissions.

### 4. Workaround (If Sandbox remains enabled)
If the sandbox cannot be disabled, you must treat the environment as "Compute Only" (CPU) and "Network Isolated" (cannot talk to host servers).
- Do NOT attempt to launch local servers.
- Do NOT attempt to manage host processes.

## Pitfalls and Fixes
- **Symptom:** Vision inference is extremely slow (e.g., < 10 t/s) despite having a high-end GPU.
  - **Cause:** `llama-server` is falling back to CPU because `/dev/kfd` is masked by the sandbox.
  - **Fix:** Disable the sandbox to allow the server to use the ROCm backend.

## Verification
1. Run `ls /dev/kfd`.
2. If it succeeds, the sandbox is effectively disabled for hardware access.
3. Attempt to `killall -0 llama-server` (signal 0) to check if you can see host processes.
