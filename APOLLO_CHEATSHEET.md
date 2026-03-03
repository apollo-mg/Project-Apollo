# 🚀 Project Apollo Terminal Cheat Sheet

This document contains a quick reference for the custom Bash aliases added to your system for managing and interacting with the Sovereign AI OS (Project Apollo).

## 🛠️ Core Aliases

| Command | Description |
|---|---|
| `apollo-sync` | Automatically syncs code from the active working directory (`~/gemini`) to the local Git repository (`~/apollo_share_dist`), performs a security audit using `qwen3-coder:30b`, generates a commit message, updates the changelog, and pushes the changes to GitHub. |
| `apollo-chat` | Drops you straight into the interactive CLI (`apollo.py`) via your virtual environment. Use this to chat with the local models directly from your terminal. |
| `apollo-dashboard` | Launches the local `live_dashboard.py` interface for real-time monitoring. |

## 🚦 Service Management

| Command | Description |
|---|---|
| `apollo-status` | Lists all active Project Apollo background processes (including active bridges, discord bots, and dashboard). |
| `apollo-discord-restart` | Kills the existing `discord_bridge.py` background process and cleanly restarts it via `nohup`, logging its output appropriately. |
| `apollo-stop-all` | Safety kill switch. Immediately terminates all active Apollo Python background processes. |

## 📜 Log Monitoring

| Command | Description |
|---|---|
| `apollo-logs-discord` | Tails the live output of the `discord_bridge.log` file. Great for monitoring vision events or debugging bot disconnects. |
| `apollo-logs-core` | Tails the `apollo_bridge.log` to monitor core API health and background task execution. |
| `apollo-logs-foundry` | Tails the last 50 entries of the `foundry_logs.jsonl` file, where the AI stores its trace loops, tool calls, and final answers. |

## 💻 Hardware & VRAM

| Command | Description |
|---|---|
| `apollo-vram` | A quick alias for `rocm-smi` to monitor GPU metrics (Temp, VRAM usage, Power) on the RX 9070 XT. |
| `apollo-models` | Maps to `ollama ps` to show you exactly which LLMs are currently loaded into VRAM. |

---
**Note:** *To apply any newly added aliases, either open a new terminal window or run `source ~/.bashrc`.*