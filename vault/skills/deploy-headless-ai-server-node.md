---
name: deploy-headless-ai-server-node
description: Provision and configure a headless Linux-based AI server node for remote LLM inference. Use when offloading heavy models or massive context windows from a primary workstation to dedicated hardware (e.g. Nvidia P100/A100).
---

# Deploying a Headless AI Server Node

Headless dedicated AI servers enable massive context windows and multi-GPU orchestration by removing the overhead of desktop environments and isolating long-running inference tasks.

## Deployment Procedure

### 1. Server Provisioning
Install Ubuntu Server (or CachyOS) and ensure the latest Nvidia drivers and CUDA Toolkit are installed.

```bash
# Check GPU recognition
nvidia-smi
```

### 2. Inference Engine Setup
Build `llama.cpp` from source specifically for the target architecture. 

```bash
# Example build for CUDA
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j $(nproc)
```

### 3. Launching the Remote API
Start `llama-server` bound to the local network IP so remote agents can access it.

```bash
./llama-server \
  --model /path/to/model.gguf \
  --host 0.0.0.0 \
  --port 8082 \
  -c 65536 \
  -sm row \
  -ngl 99
```

### 4. Environmental Context Configuration
Create a `GEMINI.md` file in the server's workspace specifically describing the hardware constraints to ensure the agent is "self-aware" of the node's physical limits.

**Mandatory Context for P100 (Pascal):**
- Note the lack of hardware tensor cores.
- Prohibit `flash_attn` or Ampere-specific optimizations.
- Instruct the agent to use `nvidia-smi` to monitor thermal safety.

### 5. Client Integration
Update the `profiles.yaml` on the client workstation to route tasks to the new node.

```yaml
server_node:
  model: "model_name.gguf"
  endpoint: "http://<server_ip>:8082/v1"
  role: "Dedicated software engineer on high-VRAM node."
```

## Hardware Specifics (Pascal/P100)

- **Power**: Ensure the use of **CPU EPS 8-pin** power adapters, NOT standard PCIe VGA cables.
- **Cooling**: Enterprise cards are passive. Use custom high-static-pressure blower fans (e.g. CPAP-style ducted shrouds) to prevent thermal throttling.

## Verification Checklist

- [ ] Does `curl http://<ip>:8082/v1/models` return a valid model list?
- [ ] Is VRAM utilization balanced across GPUs (check `nvidia-smi`)?
- [ ] Are system logs free of power delivery or thermal warnings?
- [ ] Can the agent correctly read its own `GEMINI.md` on the server?

