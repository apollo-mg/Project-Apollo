---
name: architect-edge-librarian
description: Design principles and workflow for the Edge Librarian role (asynchronous background research node).
---

## When to Use
Use this skill when designing the multi-node Sovereign Entity architecture, specifically when defining the role of low-power edge devices (Pi 5, mobile) in the data ingestion pipeline.

## Procedure

### 1. Define Node Role
The Edge Librarian is an asynchronous harvester. It does not need high speed; it needs to be relentless and power-efficient.
- **Node 1 (Architect):** High VRAM desktop (e.g., RX 9070 XT) for complex reasoning and coding.
- **Node 2 (Librarian):** Low power edge (e.g., Pi 5) for background research and data filtering.

### 2. Implementation Workflow
Design the Librarian to handle the heavy, slow work of data filtering:
1. **Epiphany Trigger:** The Daydream Daemon flags a missing piece of knowledge (e.g., "Need more data on TurboQuant math").
2. **Task Queueing:** The request is pushed to a simple task file or database.
3. **Asynchronous Harvest:** The Librarian wakes up, scrapes the URL/topic (e.g., using Jina Reader), and spends an hour reading and extracting facts.
4. **Fact Distillation:** The Librarian formats the extracted nuggets into JSON/Markdown.
5. **Ingestion:** The Distilled nuggets are pushed into the main ChromaDB for the Architect to use.

### 3. Resource-Defined Tooling (RDT)
Categorize tools based on the resources they require:
- **web_fetch_simple:** (Pi 5) Scrapes HTML using `requests`.
- **web_fetch_stealth:** (Desktop) Uses Playwright/Chromium to bypass WAFs (requires 2GB+ RAM).
- **vision_audit:** (Desktop) Uses high VRAM for OCR or image analysis.

## Pitfalls and Fixes
- **Symptom:** Librarian node falls down a "hallucination rabbit hole."
  - **Cause:** Giving a background daemon unstructured web access in an infinite loop.
  - **Fix:** Separate concerns. The Daydreamer (Air-gapped) *asks* for data; the Librarian (Internet-connected) *fetches* it. Use a `@require_human_approval` gate for external research.
- **Symptom:** Librarian is too slow for real-time interaction.
  - **Cause:** Expected behavior.
  - **Fix:** Do not use the Librarian for interactive chat. It is a background synthesizer.

## Verification
- Confirm that the Librarian node successfully distills a dense technical article into a JSON fact-nugget.
- Verify that the fact-nugget is successfully ingested into the main knowledge base.
