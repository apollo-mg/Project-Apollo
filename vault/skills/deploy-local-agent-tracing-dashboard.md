---
name: deploy-local-agent-tracing-dashboard
description: Deploy and live-patch the 'agent-lens' tracing dashboard for local LLM debugging. Use when you need to visualize agent thought traces, flame graphs, and SQLite-backed run lineages.
---

# Deploy Local Agent Tracing Dashboard

## Overview

`agent-lens` provides a localized, SQLite-backed control plane for debugging autonomous agents. It supports mid-run pausing, forking, and side-by-side trajectory comparisons.

## Implementation Procedure

### 1. Installation
Install the library into the local Python environment (e.g., `venv_cachyos`) directly from GitHub to ensure the latest features.

```bash
/path/to/venv/bin/pip install git+https://github.com/RAJUSHANIGARAPU/agent-lens.git
```

### 2. Instrumentation
Import the tracer and apply the `@trace` decorator to your LLM interaction functions.

```python
from agent_lens import trace, install

# Crucial: install() must be called to patch SDKs
install()

@trace
def call_llm(prompt):
    # Your OpenAI or Anthropic SDK call here
    pass
```

### 3. Start the Dashboard
Launch the web server using the CLI tool.

```bash
agent-lens ui --port 7878
```

## Mandatory Patches (Fidelity Fixes)

Due to version mismatches with modern Python SDKs, the following patches are required in the `site-packages/agent_lens` directory.

### 1. OpenAI SDK v1.0+ Compatibility
Comment out references to `Completions.acreate` in `integrations/openai.py` to prevent `AttributeError` crashes in modern environments.

### 2. Live Mode Event Loading
The default dashboard often fails to load events (message payloads) in "Live" mode. Patch `server.py` to embed events directly in the run details and update `dashboard/app.js` to parse them without requiring a JSON export.

## Usage Patterns

- **The Inspector:** Navigate to the **Tree** tab, select the specific `call_llm` span, then switch to **Inspector** to see the raw prompt/response.
- **Thinking Capture:** `llama-server` natively maps `<think>` tags to the `reasoning_content` field; ensure your tracer captures this field for full visibility.
- **Pause Mode:** Click the orange **⏸️ Pause** button in the UI to freeze the Python script mid-execution, allowing for prompt injection or forking.
