# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Project Apollo is a local-first, multi-node "Sovereign AI" orchestration layer that runs multi-agent LLM workloads entirely on local hardware (AMD RX 9070 XT control plane + remote Nvidia Tesla P100 worker nodes). No cloud LLM APIs are used unless explicitly authorized. This repo is the **Control Plane**: the SQLite Message Bus, agent profiles, orchestration glue, and memory/daydream subsystems.

## Commands

```bash
# Control plane lifecycle (message bus + FastContext sidecar + coordinator/WebUI)
./apollo-ctl.sh start|stop|restart|status
# Service logs and PID files land in run/ (e.g. run/message-bus.log)

# Boot diagnostics (SMVP suite; on failure writes DRIFT_WARNING.md, which agents must resolve)
./run_diagnostics.sh

# Inspect the task queue directly — the live DB is data/message_bus.db, NOT vault/message_bus.db
sqlite3 data/message_bus.db "SELECT * FROM task_queue;"

# Python: always use the project venv (no root requirements.txt; deps live in the venv)
./venv_cachyos/bin/python3 <script>.py

# Worker daemon (normally run on remote nodes; configured via env:
# NODE_NAME, NODE_ROLE, CONTEXT_WINDOW, PRECISION_BITS, MESSAGE_BUS_API)
./venv_cachyos/bin/python3 worker_daemon.py

# One-shot agent run with a profile from profiles.yaml
cd engines/open-multi-agent-upstream && npx --yes tsx examples/apollo_cli.ts --profile architect -p "<prompt>"

# Profile a new GGUF model / map hardware limits (claims all VRAM — never while serving)
./venv_cachyos/bin/python3 modules/the_scientist.py --model /path/to/model.gguf --node RX_9070_XT
```

The TypeScript orchestration framework lives in `engines/open-multi-agent-upstream/` and has its own `CLAUDE.md` with build/test commands (`npm run build`, `npm run lint`, `npm test` via vitest). **Framework edits target the `-upstream` directory**, not `engines/open-multi-agent` (the older copy still referenced by `worker_daemon.py` and `run_diagnostics.sh`).

## Architecture

**Architect/Worker topology over a SQLite Message Bus.** Three cooperating layers:

1. **The Message Bus** — `message_bus_api.py` (FastAPI, process title `apollo-message-bus`) wraps `modules/message_bus.py` (`SovereignMessageBus`), backed by SQLite in WAL mode at `data/message_bus.db`. Workers claim tasks atomically via `EXCLUSIVE TRANSACTION`; a background `timeout_checker` resets tasks stuck `in_progress` >15 min back to `pending`. Tasks carry hardware-physics requirements (`min_context`, `precision_bits`, `target_node`/`profile`) that route them to capable nodes (`fleet_status` table tracks node telemetry via `/node/heartbeat`). The API also hosts a semantic privacy filter that scrubs PII from all inbound worker payloads, plus worker provisioning endpoints (`/deploy`, `/sync/bundle.tar.gz`).

2. **The Orchestrator (TypeScript)** — `engines/open-multi-agent-upstream/examples/apollo_server.ts` is the WebSocket "Glass Cockpit" WebUI + coordinator; `apollo_cli.ts` is the terminal equivalent. Agent roles (architect, codebase_investigator, software_engineer, daydreamer, starbuck_resolver…) are defined in **`profiles.yaml`**: per-role endpoint, model, sampling params, allowed tools, and context strategy. `profiles.yaml` is the source of truth for which llama-server endpoint each role hits (endpoints/IPs drift as the fleet changes — trust the file over docs).

3. **The Workers (Python)** — `worker_daemon.py` polls the bus from remote nodes, claims a task, and shells out to `apollo_cli.ts` with the resolved profile. Remote nodes **do not share this filesystem** ("Split-Brain"): file content is exchanged via the scratchpad (`starbuck_write_scratchpad` / `starbuck_read_scratchpad` MCP tools) — agents pass scratchpad *keys* in delegations, never inline file contents.

Supporting pieces:
- `modules/` — stable core Python logic (capability router, memory/graph memory, daydream daemon, the_scientist LLMOps profiler). `archive/` and `legacy_vault/` are deprecated; ignore unless doing legacy migration.
- `engines/` — vendored/forked inference engines (multiple llama.cpp forks incl. turboquant) and agent frameworks. Each is its own embedded repo.
- `scripts/startup/` — llama-server launch scripts with tuned flags per model/hardware. The FastContext investigator sidecar (`start_investigator_sidecar.sh`) serves port 8083 locally; the main model serves 8082.
- `vault/` — memory stores (chroma, BM25, graph DBs) and prompt "skills" (`vault/skills/`).
- Project Starbuck (OS-management daemon on the P100 nodes) is a **separate isolated system**: do not modify `starbuck_daemon.py` or Starbuck OS tools from this workspace; interact only via MCP/Message Bus.

## Multi-Agent Coordination Protocol

Multiple autonomous agents (Gemini, Antigravity, Claude) work in this repo. `CHANGELOG.md` is the shared ledger:
- **Read the `[Unreleased]` section before making structural changes** to learn what other agents recently did.
- **Append a record under `[Unreleased]`** after implementing a tool, refactoring architecture, or changing configuration.

`GEMINI.md` / `.antigravity.md` are the equivalent context files for the other agents; `LOCAL_AGENT_CONTEXT.md` is the system prompt/memory anchor injected into the local Architect model — edits to it change live agent behavior.

## Context-Bleed Guardrails

The local models this repo orchestrates crash on oversized context, so the codebase enforces strict output hygiene — follow the same rules when searching/reading here:

- Exclude `venv_cachyos/`, `venv/`, `__pycache__/`, `node_modules/`, `llama.cpp/`, `whisper.cpp/`, `archive/`, `legacy_vault/`, and `engines/` (unless targeting a specific engine) from recursive searches.
- Never read `.gguf`, `.bin`, `.pyc`, or DB files; use `tail`/`head`/`grep` on large `.log`/`.jsonl` files rather than reading them whole.
- Tool output returned to local LLMs is hard-truncated (100k chars in the TSX `bash` tool; 2MB Node string cap) — preserve these limits when touching tool plumbing.
- Sub-agent IPC strips `<think>` blocks via regex before returning results to the coordinator — preserve this when touching delegation code.

## Process Control

- **Never `pkill -f` / `pgrep -f` a pattern you might be inside of.** Over ssh the searching shell is
  `bash -c '...<pattern>...'`, so the pattern matches its own command line and the kill takes down
  the session (exit 255). This happened twice: `pkill -f "llama-server.*GLM-4.7-Flash-Q6_K.gguf"`
  (2026-08-06) and `pgrep -f "pfetch.sh"` (2026-08-07) — the second *after* a written rule existed.
- Use `scripts/safekill.sh <pattern>` instead. It excludes self and every ancestor before signalling,
  is dry-run by default, and refuses runaway matches. `--exact` maps to `pgrep -x` for process names.
- Prefer `pgrep -x`/`pkill -x` (exact process name) over `-f` whenever the name alone is specific
  enough — `llama-server`, `curl`.

## Hardware Constraints That Shape Code

- The control plane GPU (16GB VRAM) comfortably runs **one large model at a time**; heavy inference is offloaded to P100 nodes per `profiles.yaml`.
- Pascal P100s crash with row-splitting: llama-server there needs `-fit off` (layer-splitting). The RX 9070 XT stability recipe is TurboQuant KV cache (`-ctk q8_0 -ctv turbo3`) + MoE micro-batching (`-ub 64`) — see `scripts/startup/`.
- Heavily-quantized local models are structurally brittle under multi-turn JSON tool schemas ("2-Bit Drunk" loops); schema validation with error feedback loops (Pydantic/Zod) is the standard mitigation pattern, and sampling params in `profiles.yaml` are empirically tuned — don't casually change them.
