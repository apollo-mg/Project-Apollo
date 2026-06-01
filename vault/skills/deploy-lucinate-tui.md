---
name: deploy-lucinate-tui
description: Configure and compile the Lucinate terminal UI as a local frontend for Sovereign LLMs. Use when replacing Claude Code with an open-source Bubble Tea TUI.
---

# Deploy Lucinate TUI

Lucinate is an open-source terminal UI (TUI) written in Go, using the Bubble Tea framework. It serves as a high-performance, customizable interactive frontend for OpenAI-compatible and OpenClaw gateways.

## Triggers

- User wants to replace proprietary CLI binaries (like Claude Code) with an open-source alternative.
- Need for a premium terminal experience with visual tool-call cards and streaming responses.
- Transitioning to a bifurcated Sovereign stack (Lucinate for "The Hands", NullClaw for "The Brain").

## Procedure

### 1. Environment Setup

Ensure the Go compiler is installed on the host system.

```bash
# CachyOS / Arch Linux
sudo pacman -S go

# Ubuntu / Debian
sudo apt install golang
```

### 2. Clone and Compile

Clone the repository into your engines directory and build the binary.

```bash
cd engines
git clone https://github.com/lucinate-ai/lucinate
cd lucinate
go build -o bin/lucinate main.go
```

### 3. Basic Usage

Test the binary by checking the help or sending a one-shot message.

```bash
# Check help
./bin/lucinate --help

# Send a one-shot message (requires a connection)
./bin/lucinate send -c local-qwen -a architect "Hello"
```

### 4. Configuration

Lucinate typically looks for connection profiles in its configuration directory (e.g., `~/.config/lucinate/` or similar). You must define a connection pointing to your local `llama-server` or `OpenClaw` gateway.

```yaml
# Example connection configuration
connections:
  local-qwen:
    endpoint: http://127.0.0.1:8082/v1
    type: openai
```

## Pitfalls and Fixes

- **Missing Go:** If `go build` fails, verify `go version` output.
- **Connection Required:** The `send` and `chat` commands require a defined `--connection`. Ensure your local LLM server is running and reachable.
- **Dependency Issues:** Go will attempt to download dependencies on the first build. Ensure internet access is available or pre-fetch modules.
