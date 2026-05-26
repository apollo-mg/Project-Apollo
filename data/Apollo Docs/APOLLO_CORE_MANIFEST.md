# Apollo Sovereign Engine - Core Manifest (Square One)

This file defines the strict, minimal set of files and directories required to run the current distributed Apollo Swarm. **Any file or directory not on this list is considered legacy cruft and is a candidate for archival.**

## 🧠 1. The Control Plane (Apollo Orchestrator)
The Node.js/TypeScript backend that houses the LLM Adapter, AgentRunner, and Sovereign Router.
- `engines/open-multi-agent-upstream/` (The entire submodule is required)
  - *Key entry points:* `examples/apollo_server.ts`, `examples/apollo_cli.ts`
- `LOCAL_AGENT_CONTEXT.md` (The dynamic memory injected into the Architect)
- `profiles.json` / `profiles.yaml` (Defines the models, roles, and allowed tools)
- `modules/capability_router.py` (The dynamic hardware routing logic)
- `modules/cognitive_escalation.py`
- `modules/pvl_engine.py` (Prior-Validation Layer)
- `src/integrity_layer.py` (Mutation Guard)
- `modules/memory_system.py`

## 👁️ 2. The UI Plane (Glass Cockpit & Dynamic Canvas)
The zero-dependency frontend that connects via WebSockets and IPC tools.
- `engines/open-multi-agent-upstream/examples/public/index.html` (The dashboard)
- `dynamic_canvas.py` (The PyQt6 GUI for the ask_user IPC integration)

## 📡 3. The Coordination Plane (Message Bus)
The SQLite-backed distributed queue that handles state-sync, heartbeats, and task delegation.
- `message_bus_api.py` (The FastAPI endpoints)
- `modules/message_bus.py` (The SQLite wrapper and logic)

## 🦾 4. The Execution Plane (Workers & Subagents)
The daemons that actually run tools, execute bash, and mutate the filesystem.
- `worker_daemon.py` (Remote task-claiming daemon for nodes like the P100)
- `modules/daydream_v2.py` (The autonomous epiphany synthesizer)
- `modules/llm_tribunal.py` (The JSON-schema rating script for daydreams)
- `modules/the_scientist.py` (The autonomous benchmarking agent)
- `run_turboquant_test.py` (The TurboQuant benchmark protocol)

## 🏛️ 5. The Memory Architecture (Seed Vault & Librarian)
The distributed memory indices and Graph architecture (GBrain integration).
- `modules/graph_memory.py` (The SQLite knowledge graph manager with the Pass 0 regex cascade)
- `sovereign_search.py` (The Librarian's Hybrid Search engine)
- `scripts/pack_seed_vault.py`
- `scripts/unpack_seed_vault.py`

## 🏗️ 6. Deployment & Configuration
The infrastructure wiring that holds the swarm together.
- `deploy/`
  - `docker-compose.yml` (Primary stack: Message Bus + Apollo Server)
  - `docker-compose.p100.yml` (Remote stack: Worker Daemon)
  - `Dockerfile.worker` (The node:22-bookworm-slim shared image)
- `bootstrap_swarm.sh` (The universal startup script)
- `.env` (Environment variables and secrets)
- `.dockerignore` / `.gitignore`
- `CHANGELOG.md` / `GEMINI.md` / `README.md` (And `data/Apollo Docs/WIKI.md`)
- `APOLLO_CORE_MANIFEST.md` (This file)
- `todo.md`

## 💾 7. State & Ephemeral Storage
These directories hold dynamic state and should be preserved but ignored by Git/Docker.
- `vault/` (The new Seed Vault storage: `bm25_index.db`, `chroma_db`, `graph_memory.db`, `hardware_profiles.db`)
- `data/` (Contains the operational `message_bus.db`)
- `chat_history/` (Saved CLI sessions)
- `models/` (The raw GGUF weight files)
- `ui_state.json` / `user_response.json` (Ephemeral IPC state for Dynamic Canvas)
- `archive/` (The graveyard for legacy files)

---
*If it's not on this list, Apollo doesn't need it to boot.*