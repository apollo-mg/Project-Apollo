# Daydream v3: Sandbox Containment & Biological Memory Decay 

## The Sovereign Entity Challenge

The Apollo Sovereign Entity relies heavily on background tasks (the "Daydream" daemon) to process historical logs, synthesize insights, and generate architectural epiphanies while the user is idle.

However, running unconstrained LLM background tasks presents two massive problems:

1. Context Window Overflows: Endless generation loops can easily blow past the 64k token limit, triggering `GGML_ABORT` or VRAM death spirals on local hardware (AMD RX 9070 XT).
2. Context Dilution: If an agent tries to synthesize everything, it eventually suffers from "Lost in the Middle" syndrome. Over-indexing on deep historical minutiae prevents the orchestrator from reasoning effectively about current, immediate architectural tasks.

## Sandbox Containment (Current Implementation)

To prevent the daemon from destroying the host environment or bloating the context window, Daydream relies on two layers of immediate containment:

### 1. OS-Level Isolation (`bwrap`)
All Daydream tasks are isolated inside a strictly configured `bwrap` (Bubblewrap) container. The daemon operates with a read-only root (`--ro-bind / /`) and a narrow write-allowlist limited to its specific git worktree, `/tmp`, and caches. A rogue write outside this boundary is physically impossible at the OS level, keeping the host system completely insulated from unguided agent execution. (Note: Kubernetes/K3s isolation is strictly reserved for the separate Project Starbuck nodes, not Daydream).

### 2. The Pydantic Shield (Schema Containment)
Outputs are strictly parsed via Pydantic/Zod schemas. If a local MoE model (like Qwen 3.6) suffers a "2-Bit Drunk" hallucination and emits shattered XML or infinite JSON strings, the Shield intercepts it. The orchestrator feeds the structural error back to the model for self-correction without crashing the system, preventing malformed tool payloads from corrupting the ChromaDB memory stores.

## Target Architecture: Biological Memory Decay (Aspirational)

While the sandbox prevents immediate system damage, long-term memory bloat remains an architectural threat. To solve this, the next iteration of Daydream will implement a system inspired by Biological Memory Decay—phasing out deep historical context in favor of highly-abstracted summaries. 

This future roadmap will execute across two new planes:

### 1. The Abstraction Crucible (Planned)
Once a Daydream daemon extracts a raw epiphany, it will pass the finding into a secondary "Crucible" agent (powered by a high-precision model). The Crucible's entire job will be to compress the raw finding into a strict, abstracted markdown summary, burning away the step-by-step trace and retaining only the architectural truth.

### 2. Chronological Decay (Planned)
As the abstractions are pushed into `CHANGELOG.md` and ChromaDB, the system will apply an Ebbinghaus decay curve. Old abstractions will be periodically re-summarized, and raw source logs older than 7 days will be automatically moved to deep, un-indexed storage (`archive/`). This guarantees that the primary Sovereign Architect only ever interacts with a highly-concentrated, low-token blueprint of the project's history.
