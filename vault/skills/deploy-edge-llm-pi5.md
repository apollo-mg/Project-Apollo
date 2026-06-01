---
name: deploy-edge-llm-pi5
description: Compile llama.cpp and deploy 1-bit LLMs on Raspberry Pi 5 for edge harvesting and background research.
---

## When to Use
Use this skill when setting up a Raspberry Pi 5 (4GB or 8GB) as a dedicated "Edge Librarian" node to handle background tasks like web scraping, data summarization, or technical fact-extraction without consuming VRAM on the primary reasoning machine.

## Procedure

### 1. Initial SSH Reconnaissance
Connect to the Pi 5 and verify resources. Note that `llama.cpp` and a 1-bit 8B model require approximately 2GB-3GB of free space and 2GB of RAM.
```bash
ssh -F /dev/null -o StrictHostKeyChecking=no <user>@<pi-ip> 'uname -a && free -m && df -h'
```
*Tip: Use `-F /dev/null` to bypass local SSH configuration errors if the host environment is restricted.*

### 2. Clearing the Runway (If Storage is Low)
If `Avail` space on `/` is less than 4GB, find and remove large legacy directories or logs.
```bash
# Find top 10 space hogs
du -sh ~/* | sort -h | tail -n 10
# Example: remove old backup directories
rm -rf ~/old_backups
```

### 3. Install Dependencies
Install essential build tools and CMake (required for modern `llama.cpp`).
```bash
sudo apt-get update && sudo apt-get install -y cmake build-essential curl git
```

### 4. Build llama.cpp (ARM NEON Optimized)
Clone the repository and perform an out-of-source build. `llama.cpp` automatically detects ARM NEON instructions on the Pi 5.
```bash
mkdir -p ~/BonPi && cd ~/BonPi
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release -j4
```

### 5. Fetch 1-Bit Weights
Download a 1-bit quantized model (e.g., Bonsai-8B Q1_0) to fit within the Pi 5's memory footprint.
```bash
mkdir -p models && cd models
curl -L -o Bonsai-8B.gguf "https://huggingface.co/prism-ml/Bonsai-8B-gguf/resolve/main/Bonsai-8B.gguf"
```

### 6. Maximize Context Window (KV Cache Optimization)
To fit large context windows (up to 65k tokens) into 4GB RAM, use asymmetric KV cache quantization.
- Set `-ctk q8_0` to compress keys.
- Set `-c 65536` for max native context.

**Launch Command Example:**
```bash
./build/bin/llama-server -m models/Bonsai-8B.gguf -c 65536 -ctk q8_0 --host 0.0.0.0 --port 8080 -t 4
```

## Pitfalls and Fixes
- **Symptom:** `make: command not found` or `Makefile:6: *** Build system changed`.
  - **Cause:** `llama.cpp` deprecated the standard Makefile in favor of CMake.
  - **Fix:** Use the `cmake` build procedure (Step 4).
- **Symptom:** `sshpass: command not found` or `ModuleNotFoundError: No module named 'pexpect'`.
  - **Cause:** Restricted agent environment prevents installing automation helpers.
  - **Fix:** Perform SSH operations manually or use plain `ssh` without password-bypassing tools if keys are not set up.
- **Symptom:** Inference is extremely slow (< 1 TPS) or crashes with OOM.
  - **Cause:** Running models > 1.5-bit or using too large a KV cache without quantization.
  - **Fix:** Switch to 1-bit (Q1_0) and ensure `-ctk q8_0` is set.

## Verification
- Verify the build finishes with `[100%] Built target llama-cli`.
- Check `free -m` during inference; `Bonsai-8B` (1.16GB) + `Q8 KV Cache` (65k tokens) should leave ~0.5GB free on a 4GB Pi 5.
