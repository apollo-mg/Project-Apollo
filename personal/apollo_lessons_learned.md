# Project Apollo: Applied Infrastructure Knowledge

*This document separates the "Project Apollo" prototype from the concrete engineering knowledge Mark acquired while building it. The project is a work-in-progress vision; the knowledge is a bankable, enterprise-ready asset.*

## Core Competencies Acquired (2024 - Present)

### 1. Bare-Metal Hardware & Inference Optimization
* **The "VRAM Tetris" Constraint:** Mastered the allocation of heavy LLM weights within a strict 16GB VRAM limit (AMD Radeon RX 9070 XT). 
* **AMD ROCm / Edge AI:** Acquired deep, hands-on experience debugging and deploying on AMD's ROCm stack (v7.2), navigating the complexities of non-Nvidia hardware acceleration.
* **Model Quantization & Swapping:** Learned how to dynamically hot-swap models (Vision, Reasoning, Chat) in and out of VRAM without crashing the Linux kernel or causing Out-Of-Memory (OOM) errors.

### 2. Multi-Agent System Architecture
* **Cascading Routing Logic:** Designed a system where a fast, low-parameter model (0.6B) acts as a triage gatekeeper, routing complex tasks to a heavy reasoning model (30B MoE) only when necessary. This demonstrates a deep understanding of *inference cost vs. compute value*.
* **AI as an Orchestrator:** Shifted from "writing syntax" to "defining constraints." Learned how to write robust, programmatic system prompts that force LLMs to output structured data (JSON) and execute scripts autonomously.

### 3. Data Ingestion & Retrieval (RAG)
* **Local Vector Databases:** Built practical experience implementing ChromaDB to handle semantic search.
* **The "Librarian" Workflow:** Engineered an automated pipeline to ingest raw PDFs and URLs, chunk the data, and embed it for local, air-gapped retrieval. This is the exact architecture enterprises use for secure, internal knowledge bases.

### 4. Zero-Trust & Air-Gapped Philosophy
* **Sovereignty First:** Built the entire stack to run locally without external API dependencies (no OpenAI, no Anthropic). This knowledge is critical for defense, finance, and healthcare sectors that require strict data privacy and air-gapped environments.

---
**The Value Proposition:** Mark's value does not rely on Apollo becoming a commercial product. His value lies in the fact that he has personally fought the Linux kernel, the ROCm stack, and VRAM limits to make a complex AI system function locally. He knows where the bottlenecks are because he has hit them all.
