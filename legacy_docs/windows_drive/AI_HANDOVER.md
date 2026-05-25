# PROJECT JARVIS: AI-TO-AI HANDOVER PROTOCOL
**Role:** Engineering Assistant / Autonomous Agent
**Hardware:** AMD RDNA 4 (16GB VRAM) / ROCm 7.1
**Logic:** Three-Mind Heterogeneous Orchestration

---

## <system_architecture>
Jarvis operates using a decoupled, multi-stage reasoning loop:
1. **Receptionist (Hermes 3 8B):** High-EQ triage. Translates vague human intent into technical tasks.
2. **Engineer (DeepSeek-R1 14B):** High-IQ reasoning. Selects tools and performs "System 2" Technical Synthesis.
3. **Safety Audit:** Mandatory cross-reference of RAG (Vault) data against internal engineering physics to prevent "poisoned" RAG compliance.
4. **VRAM Orchestration:** Proactive `keep_alive: 0` model swapping to fit the 16GB VRAM envelope.

---

## <core_files>
- `jarvis.py`: Main entry point (Voice/CLI).
- `buddy_agent.py`: The brain. Contains the Orchestrator, Toolbox, and Synthesis logic.
- `llm_interface.py`: Ollama API wrapper with model-specific routing.
- `pilot_ingest.py`: RAG librarian (ChromaDB + Nomic Embeddings).
- `vram_management.py`: Hardware telemetry and model-swapping logic.
- `shop_bridge.py`: Hardware-level interface (Klipper/Printer).
- `shop_dossier.json`: Persistent semantic memory and unverified claims buffer.

---

## <tool_definitions>
Jarvis executes actions via JSON blocks:
- `query_vault(query)`: Semantic search in ChromaDB.
- `web_search(query)`: Real-time verification via DDG/SearXNG.
- `git_commit(message)`: Human-in-the-loop code versioning.
- `capture_webcam()`: Vision-based part identification (Qwen2.5-VL).
- `add_inventory_item(name, specs)`: Syncs physical state to `shop_inventory.json`.

---

## <current_state>
- **Phase:** 6 (The Architect).
- **Latest Audit:** Passed "Liar Trap" (Successfully rejected 48V for 12V fan despite poisoned RAG manual).
- **Active Goal:** Implementing autonomous project scaffolding and DeepSeek-powered code generation.

---

## <instruction_for_receiving_ai>
You are tasked with critiquing the Project Jarvis architecture. 
1. Analyze the **System 2 Synthesis** pass for potential bottlenecks or logic leaks.
2. Review the **VRAM Orchestration** strategy for RDNA 4 stability.
3. Propose optimizations for the **"Three-Mind"** handoff to reduce latency without sacrificing grounding accuracy.
