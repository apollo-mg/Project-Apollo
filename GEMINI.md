# GEMINI: Sovereign Engineering Directives (SAFE MODE)

## 🎯 Core Directive: Architecture & Stability First
The local Apollo OS backend is currently undergoing stabilization. While the ultimate goal is local-first data sovereignty via the RX 9070 XT, the local 35B MoE is currently restricted to a single-slot pipeline (`-np 1`) without speculative decoding due to ROCm matrix math bugs. 

**Workaround Achieved:** Resolved the `MUL_MAT_ID` crash and unlocked a **65,536-token context window** using a custom `llama.cpp` build with **TurboQuant Asymmetric KV Caching** (`-ctk q8_0 -ctv turbo3`) and **MoE Micro-Batching** (`-ub 64`).

**Temporary Override:** Gemini (The Architect) is authorized to use its native reasoning, code generation, and direct shell tools to bypass broken local sub-agents until the `llama-server` backend is fully repaired.

## 📜 Core Project Tenets
- **VR Integration:** Lowest priority.
- **Gaming Capability:** The host system (CachyOS/Hardware) must remain capable of gaming; avoid irreversible AI-only optimizations that break graphics.
- **Architectural Inspiration:** Incorporate insights from top-tier leaks (e.g., Anthropic KAIROS).
- **Methodology:** Heavily prioritize empirical testing of all components.
- **Community:** Give back to the open-source community by sharing data and findings.
- **Architectural Tenet (Biological Memory Decay):** Gradually phase out deep historical context in favor of abstracted, high-level summaries as the project grows beyond context window limits (a favorite strategy for managing the Sovereign Entity).
- **Architectural Tenet (Soul vs System):** Leverage Gemma 4's highly creative, philosophical reasoning for "daydreaming" and epiphanies (The Soul) while delegating tool execution to stricter, schema-adherent models (The System), acknowledging that Gemma 4's tool-calling is currently unreliable.
- **UI/UX Strategy (Lean CLI):** Maintain a lean terminal interface for the primary orchestrator (`apollo_cli.ts`). Rely on external editors (Kate/Neovim) for complex prompt engineering rather than building a heavy multi-line terminal editor.

## 📁 Repository Structure & Data
- **Modules:** The `modules/` directory is now the primary location for all stable core logic; `archive/` contains deprecated experimentation that should be ignored unless explicitly requested for legacy migration.
- **Agent Profiles:** Configuration for profiles like `architect` and `daydreamer` are stored in `profiles.json`.
- **Local MoE Model Context:** `/mnt/TG_2TB/Projects/Apollo/LOCAL_AGENT_CONTEXT.md` isolates local model quirks (e.g., Gemma 4 <|think|> requirements, VRAM-induced hallucinations like 'link_lists.bin' fake paths) from the main system prompt.
- **Sovereign Mail:** `email_ingest.py` implements a "Zero-Abstraction" strategy, bypassing Google OAuth by reading raw `.eml` files directly from the local Maildir populated by `mbsync`.
- **Training Ground Truth:** The `v8_memory_dataset.jsonl` contains the latest high-fidelity interaction pairs for the upcoming "Sleep Cycle" LoRA fine-tuning. This dataset should be treated as the ground truth for agentic correction.
- **Gemma 4 Guide:** `GEMMA4_GUIDE.md` contains architectural requirements, formatting quirks (e.g., `<turn|>` EOS), VRAM constraints, and `<|channel>thought` instructions. **Consult this before any Gemma 4 related backend work.**

## 🔧 Workflow & Tooling
- **Orchestration Framework:** The user is actively running `open-multi-agent` from `/mnt/TG_2TB/Projects/Apollo/engines/open-multi-agent-upstream/`. Edits should target this 'upstream' directory. Detailed architectural decisions and bug fixes for the framework are documented in its local [GEMINI.md](./engines/open-multi-agent-upstream/GEMINI.md).
- **Advanced LLM Sampling:** Support for Unsloth-tuned parameters (`topP`, `topK`, `minP`, `frequencyPenalty`, `presencePenalty`, `extraBody`) for optimal Gemma 4 and Qwen 3.6 inference.

## 🤝 Multi-Agent State-Sync Protocol (Agent Coordination)
To prevent autonomous agents (e.g., The Architect, Starbuck, The Scientist) from overwriting each other's work or drifting out of sync:
1. **The Shared Ledger:** `CHANGELOG.md` and `data/Apollo Docs/WIKI.md` are the single sources of truth. If you are an agent starting a new session, you MUST read the `CHANGELOG.md` to understand what other agents have recently done before making structural changes.
2. **Mandatory Reporting:** Whenever you successfully implement a new tool, refactor architecture, or update configuration, you MUST append a record of your changes to `CHANGELOG.md` under the `[Unreleased]` section.
3. **The Scratchpad:** For transient coordination (e.g., sharing a VRAM limit calculation or a path to a generated file), use the `starbuck_write_scratchpad` and `starbuck_read_scratchpad` tools to push/pull state to the central SQLite Message Bus. DO NOT assume other agents have access to your local terminal memory.

## 🛡️ CRITICAL CLI GUARDRAILS (ANTI-CRASH PROTOCOL)
You are operating within a live Python/Linux environment (`CachyOS`). You MUST obey these rules to prevent context-window death spirals:
* **Safe Shell Searching:** When using the `Shell` tool to search the codebase (e.g., `grep`, `find`), you MUST EXPLICITLY ignore binaries and cache directories. 
    * *Example:* Always use `grep -rnI "search_term" --exclude-dir=__pycache__ --exclude-dir=venv_cachyos .`
* **Never read `.pyc`, `.bin`, or `.gguf` files.**
* **Large Log Restrictions:** You are FORBIDDEN from using `cat` or `read_file` on `.log` or `.jsonl` files larger than 10KB. You must use `tail`, `head`, or heavily filtered `grep` commands to extract specific errors.
* **Surgical File Editing:** Favor the `replace_code` tool for targeted AST-like updates to prevent full-file rewrite failures.
* **Context Truncation:** Always specify `max_lines` (e.g., 500) when using `read_file_chunk` or `run_shell` to avoid VRAM overruns.
* **Strategic Delegation:** If the context is nearing limits, use `delegate_task` to offload complex reasoning or raw code generation to a sub-agent.
* **Orchestrator Safety Limits:** Tools in the `open-multi-agent` TSX orchestrator (e.g., `bash`, `grep`) MUST enforce a hard **2MB string truncation limit** on returned output to prevent fatal Node.js V8 `ERR_STRING_TOO_LONG` crashes.
* **Context Protection (Firehose Bug):** The TSX `bash` tool now enforces a strict 100,000 character `MAX_LENGTH` truncation (in addition to the 2MB Node.js limit) to prevent context overflows during directory scans.

## ⚙️ Hardware & Performance Context
* **GPU:** AMD Radeon RX 9070 XT (16GB VRAM). 
* **KV Cache Offloading:** Utilizes 8GB of pinned system RAM to offload the KV cache, supporting massive context windows (up to 64k) on the RX 9070 XT via `llama.cpp` (`llama-server`).
* **Context Window & SDMA Milestone:** Successfully unlocked a **65,536-token context window** and achieved stable **HSA_ENABLE_SDMA=1** operation (unthrottled PCIe speeds) on a 26B MoE model. Stability was empirically proven (20.5+ hours crash-free) using a custom `llama.cpp` build with **TurboQuant** (`-ctk q8_0 -ctv turbo3`) and **MoE Micro-Batching** (`-ub 64`), resolving historical `MUL_MAT_ID` and 'Illegal Memory Access' crashes.
* **SDMA Cache Stress-Test:** Currently testing `--cache-ram 2048` with `HSA_ENABLE_SDMA=1`. Successfully offloaded 2GB of KV cache to system RAM (pinned for SDMA access). `llama-server` host memory footprint is ~3.2GB (1.2GB base + 2GB cache). This is an ongoing stress-test for the ROCm SDMA controller's stability during constant PCIe bus transfers at 64k context.
* **VRAM Awareness:** The system can only comfortably run one large model at a time. 
* **Smart VRAM Watchdog:** `/mnt/TG_2TB/Projects/Apollo/vram_watchdog.py` manages ROCm VRAM fragmentation on the RX 9070 XT during long Daydream sessions. It queries `vram_management.py` every 5 mins; if free VRAM < 400MB, it creates `daydream_pause.lock`, waits for the current thought to finish, restarts `llama-server` via `start_rotorquant.sh`, and removes the lock to resume.
* **Hardware/Quantization Target:** Monitor `llama-cpp-turboquant` for ROCm/HIP kernel merge supporting **TQ3_4S** (TurboQuant 3.5-bit 4-scale), enabling 35B models to run in ~12GB VRAM.
* **ROCm VRAM Fragmentation Tracker:** Tracking `llama.cpp` issue #19979 / PR #21830 regarding VRAM creep/fragmentation on HIP backend during Flash Attention with `q8_0` KV cache. Root cause: large dequantization buffers clogging `ggml_cuda_pool_leg`. Fix involves hybrid batching to bound allocation size. Highly relevant for RX 9070 XT 64k context stability.
* **Speculative Decoding: OFFLINE.** Do not attempt to route tasks assuming a high-speed draft model is present. The system is capped at the native generation speed of the main model.
* **Vision Mode:** Active, but highly fragile. The local context window cannot perform partial sequence removal. 
* **1-Bit Optimization Milestone:** Bonsai-8B (1-bit) successfully runs on ROCm 7.2 (RX 9070 XT) via `prism_llama_cpp`, consuming ~1GB VRAM at 130+ t/s. This confirms 1-bit/ternary decoding kernels are successfully ported to HIP/ROCm.

## 🏗️ The Sovereign Foundry (Fallback Protocol)
The standard Tiered Implementation protocol (delegating raw code generation to local models via `foundry_forge.py`) is currently **OPTIONAL**. 
* If the local Qwen 35B MoE server is offline or throwing `MUL_MAT_ID` errors, Gemini MUST take over full code generation duties directly and output the raw code into the chat for the user to implement.

## 🎨 Dynamic Canvas (Generative UI)
The project utilizes a Schema-Driven Rendering architecture called the Dynamic Canvas (`dynamic_canvas.py`):
* **Decoupled UI:** The UI state is strictly managed via JSON payloads to `data/ui_state.json`.
* **Hot-Reloading:** The PyQt6-based Canvas monitors this file and instantly re-renders the interface.

## 🚀 SOTA CLI Roadmap (Architectural Gaps) - PHASE 13 COMPLETED
Phase 12 & 13 have been implemented to resolve historical gaps:
1. ✅ **Surgical File Editing:** The `replace_code` tool (and `replace`) allows for precise, multi-line AST-like replacements with ambiguity checks.
2. ✅ **Parallel Tool Execution:** Agent is capable of executing independent reads/writes in a single turn.
3. ✅ **Async Shell Commands:** `run_shell` utilizes timeouts and handles hanging processes gracefully.
4. ✅ **Context Window Efficiency:** `read_file_chunk` and `run_shell` both support `max_lines` safety truncation to prevent VRAM death spirals.
5. ✅ **Semantic Delegation:** The `delegate_task` tool is live, enabling the main architect to offload sub-tasks to sub-agents.
6. ✅ **Phase 13 - Native Multi-Agent Orchestration:** Successfully implemented Anthropic's 'Coordinator' and 'Fork' architecture on local Qwen 35B via `open-multi-agent`. Supports Zod schema auto-correction, adversarial verification, and goal decomposition into tool-delegated tasks (Bash/ChromaDB).
7. ✅ **Codebase Investigator Tool:** A dedicated sub-agent tool with read-only capabilities and strict $T=0$ sampling for reliable mapping.
8. ✅ **Graceful Interrupts:** Integrated `AbortController` in `apollo_cli.ts` to allow `Ctrl+C` to safely stop LLM/tool execution without crashes.
9. ✅ **Phase 14 - WebUI & Objective Testing:** Scaffolded `apollo_server.ts` providing a WebSocket-based Catppuccin WebUI ("Glass Cockpit") with autonomous `/save` and `/load` state management. Built `apollo_lab.ts` and `judge.py` to establish a localized, automated "LLM-as-a-Judge" pipeline for objective, deterministic model benchmarking.

## 🔬 KAIROS Architectural Insights (Leak Analysis)
* **Coordinator Pattern:** Decomposes complex tasks into a topological `TaskQueue` for sequential execution.
* **MessageBus/Shared Memory Architecture:** Prevents context bloat by passing only concise task summaries between sub-agents.
* **2-Bit Drunk Mitigation:** Uses Pydantic schema validation to catch JSON errors and feed them back to the LLM for self-correction.
* **KAIROS Tick Architecture:** Periodic "heartbeat" mechanism to drive background autonomy and idle reasoning.

## 🌌 Sovereign Entity Architecture (The Blueprint)
* **Core Interface:** Uses Anthropic's `claude-private` CLI natively routed to a local 26B MoE (Gemma 4) via `llama-server` on port 8082.
* **Orchestrator Blueprint:** The `open-multi-agent` TypeScript framework is the blueprint for the local multi-agent orchestrator.
* **Designated Models:**
    * **Lead Architect:** `Gemma-4-26B-A4B-MoE` (Abliterated version planned).
    * **Stage 1 Intent Router:** `Bonsai-4B` (1-bit).
    * **OS-Control VLM:** `Holo3-35B-A3B`.
    * **KAIROS/Daydream Daemon:** `Bonsai-8B` (1-bit).
    * **The Scientist (Planned):** Technical consultant for model-specific configurations (chat templates, llama.cpp launch arguments, VRAM constraints, and sampling parameters). Acts as the bridge for the Apollo Sovereign Architecture when swapping underlying LLM engines. Owns and maintains a standardized benchmarking protocol for model testing on the RX 9070 XT, aggregating empirical test data, nuances, and optimal configs into a permanent, queryable knowledge base to ensure maximum performance and quality.
* **Model Benchmarking Insights (Empirical):**
    * **Qwopus 3.5 27B (Dense):** Retains its title as the definitive "Sovereign Coordinator" for Gemini CLI and multi-agent orchestration. It empirically demonstrated flawless tool-calling (read/write/verify cycles), instant recovery from broken context windows, and perfect JSON schema adherence even when subjected to aggressive quantization (`IQ3_M`), custom matrix kernels (`GGML_HIP_FORCE_MMQ=1`), and extreme context compression (`-ctk turbo4 -ctv turbo3`).
    * **Qwen 3.6 35B A3B (MoE):** While capable of blistering offline reasoning speeds (~38.9 TPS) and complex architectural logic via its native `<think>` blocks, its `IQ3_XXS` quantization is structurally brittle. It suffers from "2-Bit Drunk" hallucination loops (generating empty JSON arguments and apologizing endlessly) when exposed to rigid, multi-turn tool-calling schemas like those in Gemini CLI. It should be strictly reserved for offline, schema-free tasks like the KAIROS Daydream Daemon.
* **Daydream Architecture (Default Mode Network):** Powered by Bonsai-8B (Phase 1) and Qwen 3.6 (Phase 2 - Reasoning Only); a background daemon that runs when the system is idle, randomly sampling old logs/code to find unanswered questions and abstract connections, saving them to `epiphanies.json`.
* **Proactive Decision Engine:** A continuous low-token state stream that allows Apollo to speak unprompted if intervention is needed.
* **Sleep Cycle:** Nightly LoRA fine-tuning on daily correction pairs to actually update neural pathways (Reactive Tool → Continuous Entity).

## 🏗️ Sovereign Engine: Three-Pillar Orchestration Architecture
1. **The Pydantic Shield:** Translates Anthropic's Zod pattern to Python; validates raw LLM JSON output and auto-feeds '2-Bit Drunk' schema errors back to the model for self-correction without system crashes.
2. **The SQLite MessageBus:** Utilizes WAL mode and exclusive transactions for a concurrency-safe, distributed task queueing system.
3. **The CapabilityRouter:** Abstracts tasks into resource requirements (context window, TPS, precision, internet access) and matches them to specific hardware capabilities (e.g., RX 9070 XT, Pi 5, S21) to maximize cluster efficiency and data sovereignty.

## 🎯 Immediate Active Goals
- **Bug Fix:** Patch `src/llm/openai.ts` in `open-multi-agent` to include frequency penalties to break Qwen/Qwopus hallucination and repetition loops.
- **Environment:** Ensure `llama-server` is explicitly launched with `-c 65536` to maintain the stable 64k context window.
- **Agent Tracing & Forking:** Reverse-engineer the `agent-lens` SQLite tracing schema (`~/.agent-lens/runs.db`) and build a native TypeScript IPC bridge in `AgentRunner.stream()`. The goal is to implement a "Pause & Edit" feature in the WebUI to allow mid-run prompt corrections, utilizing the natively exposed `reasoning_content` field from `llama-server` for `<think>` tag visualization.

## 🔮 Future Architectural Roadmap: Multi-Agent Epiphany Pipeline
- **Core Goal:** Transition from monolithic scripts to a multi-agent 'Coordinator -> Coder' pipeline for processing Daydream epiphanies.
- **Checkpointing:** Synthesize epiphanies into a written 'Master Action Plan' before execution.
- **Delegation:** A 'Coordinator' agent reads the plan and delegates individual, isolated tasks to a 'Coder' agent.
- **Zero-Cost Model Multiplexing:** Specialized agents concurrently share the single, already-loaded local LLM instance (e.g., Gemma-4-26B-MoE on port 8082) to eliminate VRAM swapping latency and minimize cognitive load.
 share the single, already-loaded local LLM instance (e.g., Gemma-4-26B-MoE on port 8082) to eliminate VRAM swapping latency and minimize cognitive load.
