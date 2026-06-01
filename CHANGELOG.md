# Apollo Sovereign Entity Architecture - Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **FastMCP NullClaw Bridge:** Created `apollo_bus_mcp.py` to seamlessly connect the 678KB compiled Zig `nullclaw` worker daemon on the P100 to the SQLite Message Bus using stdio tools (`claim_next_task`, `submit_task_result`, `query_seed_vault`, `read_scratchpad`, `write_scratchpad`).
- **Capability Physics Telemetry:** Upgraded the `fleet_status` table in `message_bus.db` to track multi-tiered memory (`max_slot_context`, `hot_kv_tokens`, `warm_kv_tokens`), `active_model_archetype`, and `kv_precision`. 
- **Automated Heartbeat:** Added an asynchronous background thread to `apollo_bus_mcp.py` that polls `llama-server` API (`/props`, `/slots`) and host OS processes every 5 seconds to dynamically update the Capability Physics in the database.

### Changed
- **UUID Task Dispatching:** Upgraded `message_bus.py` schema from integer IDs to `UUIDv4` strings. This bypasses NullClaw's internal PII Regex scrubber without disabling its critical security isolation layer. Updated `dispatch_task.ts` to sync with `vault/message_bus.db` natively.
- **Fleet Status Telemetry:** Implemented a new `fleet_status` table in the SQLite Message Bus to track remote node health.
- **Heartbeat API:** Added `POST /node/heartbeat` and `GET /node/status` to `message_bus_api.py` allowing remote Worker nodes (like Starbuck) to register their CPU/RAM load, active status (idle/executing_tool), and OS version for the Glass Cockpit UI's "Fleet Map".

### Changed
- **Advanced LLM Sampling (PR #163):** Fully plumbed sampling parameters (`temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, `min_p`, `top_k`, and `extraBody`) from `profiles.yaml` through the `open-multi-agent` adapter to `llama-server`. Stripped `parallel_tool_calls: false` override to allow model flexibility.
- **Subagent Framework Optimizations:** 
  - **Auto-Bootstrapping:** `codebase_investigator` now automatically executes `tree -L 2` and injects it into its starting prompt to prevent "flying blind" on turn 1.
  - **Auto-Testing:** `software_engineer` now accepts an optional `test_command` via JSON schema that is executed natively post-generation to empirically validate code.
  - **IPC Stripping:** Implemented RegEx sanitization across `delegate_task` and sub-agents to strip `<think>` blocks from payload responses, preventing context bloat for the Lead Architect.
- **Sovereign Coordinator Prompt Refinements:** Added strict mandates to `LOCAL_AGENT_CONTEXT.md` explicitly instructing the Architect to trust its subagents and never run redundant `file_read`/`bash` manual verifications on their outputs unless a test fails.
- **P100 Inference Offloading:** Updated all `profiles.yaml` endpoints to route LLM inference to the headless P100 node (`http://10.0.0.71:8082/v1`), freeing the 9070 XT desktop for UI and Message Bus workloads.
- **Subagent Multi-Node Routing:** Fixed a bug in `codebase_investigator` and `software_engineer` where the tools ignored the `endpoint` key in `profiles.yaml`. Subagents will now correctly route API requests to remote nodes (like the RX 9070 XT rig) instead of falling back to localhost.
- **Context Bleed Protection:** Enabled `compress_tool_results: true` in `profiles.yaml` and implemented support for it within `codebase_investigator` and `software_engineer` to prevent raw file contents and terminal outputs from permanently bloating the subagent's local history array and causing `llama-server` 50K slot truncation errors.
- **Reasoning Stream Parsing:** Updated `OpenAIAdapter` (`src/llm/openai.ts` and `openai-common.ts`) to capture `reasoning_content` from the OpenAI wire format and wrap it in `<think>` tags. This ensures `llama-server` `<think>` blocks are correctly preserved and rendered in the CLI, and fixes a bug where subagent responses were treated as empty strings when maxTurns were exhausted.
- **PTC Triple-Quote Hallucination Fix:** Added a fallback RegEx parser in `openai.ts`, `openai-common.ts`, and `text-tool-extractor.ts` to intercept malformed `run_python_script` and `bash` tool calls containing raw Python docstrings (`"""`) or unescaped newlines. This prevents `JSON.parse` failures from silently stripping valid tool calls to empty objects.
- **Anti-Hallucination Protocol Enforcement:** Rewrote the system prompt for the `codebase_investigator` subagent to enforce strict anti-hallucination guardrails: agents are now explicitly forbidden from guessing file paths via naming conventions and must verify file existence using `glob` or `bash` (`ls`) prior to drafting architectural reports. Increased `maxTurns` limit from 15 to 30.
- **Daydream Daemon v2:** Deployed `daydream_v2.py` with dual-pass pipeline (Dreamer -> Filter via Guided Decoding) and survivability gating (CPU/GPU EWMA thresholds) to optimize prompting for the Gemma 4 MOE architecture (`Gemma4-31b`) and mature its architectural logic.
  - Overhauled the system prompt to enforce strict deterministic execution (`<|think|>` tags, no meta-commentary, explicit CachyOS grounding).
  - Implemented parsing for `reasoning_content` to separate the internal monologue from the final JSON epiphany payload.
  - Adjusted sampling parameters (`temperature: 1.0`, `top_k: 64`) to encourage broader associative connections during idle states.
  - **Cognitive Depth:** Upgraded `get_random_memories()` to use "Associative Daydreaming" (pulling 1 random seed memory and performing a ChromaDB semantic similarity search to find connected memories) instead of purely random sampling.
  - **Endpoint Decoupling:** Removed hardcoded URLs and model names. The daemon now dynamically imports `llm_interface.get_config()` to query the currently active Sovereign Entity model.
  - **Parsing Robustness:** Replaced greedy RegEx JSON extraction with strict first/last curly brace indices (`.find('{')` and `.rfind('}')`) to prevent catastrophic parsing failures if the model outputs trailing characters before EOS.

### Added
- **Starbuck OS Management Layer:** Implemented "Option 2" Subagent Routing for autonomous OS repair.
  - Added `starbuck_resolver` profile to `profiles.yaml` with strict sysadmin instructions for handling `apt`/`pacman` failures.
  - Created `starbuck-resolver.ts` subagent tool in the TypeScript orchestrator, natively connecting to the Starbuck FastMCP daemon via `stdio`.
  - Added `starbuck_execute_fix` MCP tool to `starbuck_daemon.py`, strictly gated at YOLO Level 3 for raw package manager bash commands.
- **Semantic Delegation Routing:** Solved subagent routing overlap by defining hard semantic boundaries via Zod schemas and a Delegation Matrix in `LOCAL_AGENT_CONTEXT.md` / `profiles.yaml` (routing OS tasks to `starbuck_resolver` and coding tasks to `software_engineer`).
- **Project Starbuck MCP Daemon:** Initialized `starbuck_daemon.py` using `FastMCP` to grant the local LLM autonomous Linux Sysadmin capabilities over `stdio`.
- **YOLO Permission Hierarchy:** Gated all Starbuck tools via the `STARBUCK_YOLO_LEVEL` environment variable (Levels 0-3) to enforce strict safety boundaries.
- **Strictly-Typed Sysadmin Tools:** Implemented JSON-schema validated tools (`starbuck_manage_service`, `starbuck_read_journal`) to interact securely with `systemctl` and `journalctl`, bypassing generic bash execution to leverage Apollo's Pydantic Shield.
- **Agentic Scratchpad:** Centralized transient swarm memory via new `scratchpad` table in the SQLite Message Bus, equipped with REST endpoints (`/scratchpad`) and matching MCP tools for cluster-wide read/write operations.
- **Swarm Unification (Zero-Config Edge Nodes):** Refactored the `open-multi-agent` orchestrator and sub-agents to dynamically fetch their configurations (Tools, Temperature, System Prompts) from the `message-bus` FastAPI container on boot, completely eliminating the "Split-Brain" config risk across the 9070 XT and P100 nodes.
- **Async Tool Streaming:** Integrated real-time WebSockets via the `onStream` callback to pipe raw `stdout` from native Linux shell commands directly to the Glass Cockpit UI while preserving strict token truncation for the LLM context.
- **LLM Tuning:** Added `frequency_penalty` and `presence_penalty` parameters to `open-multi-agent`'s `OpenAIAdapter` and the Gemini CLI `AgentConfigDialog` to enable granular tuning of output repetition.
- **Scientist Agent (Planned):** Technical consultant for managing model configurations (sampling, templates, VRAM) when swapping LLM engines.
- **Cognitive Escalation:** Implemented `modules/cognitive_escalation.py` with `CognitiveEscalation` class that monitors for critical system/hardware errors (memory pressure, CPU bottlenecks, disk exhaustion, thermal limits) and triggers Deep Reasoning capabilities (e.g., DeepSeek-R1) for emergency-level cognitive processing. Features include:
  - **SystemHealth dataclass:** Real-time metrics for RAM/CPU/disk usage, temperature, network latency, and active processes
  - **EscalationLevel enum:** Four-tier emergency classification (WATCH, CRITICAL, EMERGENCY, CATASTROPHIC)
  - **CognitiveEscalation class:** Core monitoring engine with configurable thresholds for system resource limits
  - **Automatic deep reasoning trigger:** When critical thresholds are breached, the system automatically escalates to the Architect tier (high-compute, 30B+ models) for emergency cognitive processing
  - **Emergency handlers:** Callback-based response system for specific escalations levels (catastrophic, emergency, critical)
  - **Thread-safe operations:** Lock-based synchronization for multi-threaded escalations and emergency response coordination

## [1.0.0] - 2026-05-XX
### Added
- **Phase 1 Complete:** Synthesizer agent successfully parsed 48 Daydream epiphanies into `master_action_plan.md`.
- **Zero-Cost Multiplexing:** Implemented `apollo_coordinator.ts` dual-agent orchestration loop.
- **Semi-Formal Reasoning:** Injected Meta's 'Logical Certificate' requirement into the Coder agent's system prompt to prevent hallucination loops.
- **State-Sync Protocol:** Established mandatory changelog tracking for all autonomous agent actions.
- **Driver-Kernel Alignment Check:** Implemented `scripts/driver_kernel_alignment_check.py` to validate ROCm/HIP versions against kernel drivers, preventing 'Ghost' configurations where hardware-software compatibility is compromised.
- **Hardware Orchestration Layer:** Implemented `HardwareOrchestrator` class in `src/hardware/hardware_orchestrator.py` providing unified API for physical device adjustments (audio gain, camera exposure, etc.) with HIP synchronization barriers, resource management, and thread-safe hardware operations.
- **Auto-Fallback Mechanism:** Implemented `src/agent/mha_fallback.py` with `AutoFallbackManager` class that automatically switches to hardware-aligned model variants (e.g., SDXL-Turbo) when VRAM margins are breached, ensuring continuous operation under hardware constraints.
- **Tiered Memory System:** Implemented `src/modules/memory_system.py` with three-tier memory architecture:
  - **Tier 1 (Working Buffer):** In-memory sliding window (LRU) for immediate context with configurable window size and automatic eviction.
  - **Tier 2 (Associative Cache):** SQLite-based short-term memory layer with vector embeddings for semantic search and associative recall.
  - **Tier 3 (Long-Term Knowledge):** ChromaDB-based persistent storage with JSON file-based vault for permanent knowledge retention.
  - **Unified Interface:** `TieredMemorySystem` class providing unified access with automatic tier promotion/demotion based on access patterns.
- **Prior-Validation Layer (PVL) Engine:** Implemented `modules/pvl_engine.py` with `PriorValidationLayer` class that detects high-risk contexts (hallucination triggers, edge-case patterns) and injects anti-prior instructions into the system prompt to prevent cognitive errors. The PVL acts as a pre-computation safety layer that validates the current context before allowing the cognitive tier to proceed.
- **Cognitive Escalation:** Implemented `modules/cognitive_escalation.py` with `CognitiveEscalation` class that detects critical system/hardware errors (memory pressure, I/O bottlenecks, resource exhaustion) and escalates them to a higher reasoning tier (Deep Reasoning, e.g., DeepSeek-R1) for analysis and resolution. Part of the Reflex Arc (Error-to-Model Feedback) protocol with automatic error classification, deep reasoning tier invocation, and error-to-model feedback loop.
- **Mutation Guard:** Implemented `src/integrity_layer.py` with `MutationGuard` class that distinguishes between 'Self-Correction' (intentional architectural decisions) and 'Systemic Mutation' (unintended systemic mutations) during code-writing tasks. The guard analyzes code changes to determine if they represent intentional architectural decisions versus unintended systemic mutations that could compromise system integrity. Features include:
  - **MutationType enum:** Classifies mutations as SELF_CORRECTION, SYSTEMIC_MUTATION, ARCHITECTURAL_DECISION, or TEMPORARY_FIX
  - **MutationGuard class:** Core analysis engine that extracts features from code changes, classifies them as intentional self-corrections or unintended systemic mutations, and blocks or integrates them accordingly
  - **IntegrityLayer class:** High-level interface providing the surgical execution arm for mutation analysis with strict mode enforcement
  - **Thread-safe registry:** Maintains separate registries for self-corrections, systemic mutations, blocked mutations, and architectural decisions
  - **Automatic blocking:** Systemic mutations are automatically blocked to prevent compromise of system integrity
- **Fleet Orchestrator:** Implemented `fleet_orchestrator.py` providing a unified interface for managing the complete lifecycle of AI model deployment (Boot → Train → Zip → Upload → Verify). Features include:
  - **Bootstrapper:** Initializes and configures the environment for model training and deployment with GPU detection and checkpoint management
  - **Trainer:** Trains models and produces trained artifacts with configurable epochs, batch size, and learning rate
  - **Packager:** Packages trained artifacts into distributable tar.gz format with integrity verification
  - **RepositoryUploader:** Handles uploading to repository with SHA-256 checksum computation for integrity verification
  - **IntegrityVerifier:** Verifies integrity of deployed assets with configurable expected checksums
  - **Lifecycle Management:** `FleetOrchestrator` class orchestrates the complete Boot → Train → Zip → Upload → Verify pipeline with state tracking and checkpoint resumption capabilities
