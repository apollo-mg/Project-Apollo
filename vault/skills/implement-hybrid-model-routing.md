---
name: implement-hybrid-model-routing
description: Procedural implementation of hybrid model routing in Gemini CLI to offload utility tasks (e.g., web scraping) to fast cloud models while maintaining a local sovereign model for primary reasoning.
---

## When to Use
- When using a local model (Sovereign) that is token-constrained or has no internet access.
- When performing token-heavy utility tasks like web scraping, HTML parsing, or large document summarization.
- To avoid quota limits or high costs on primary cloud models by using "Flash" variants for sub-tasks.

## Procedure
1. **Identify Routing logic**: Locate the router implementation, typically in `packages/core/src/core/routerContentGenerator.ts`.
2. **Define Utility Model Names**: Establish convention for utility-specific model names (e.g., `web-fetch`, `summarizer-utility`).
3. **Intercept Request**: In `generateContent` and `generateContentStream`, add a check for the utility model name.
    ```typescript
    if (request.model === 'web-fetch') {
      const utilityRequest = { ...request };
      utilityRequest.model = 'gemini-3-flash-preview'; // Force fast/cheap model
      return this.fallback.generateContent(utilityRequest, userPromptId, role);
    }
    ```
4. **Preserve Sovereign Route**: Ensure local/sovereign models (e.g., prefixed with `openai/` for local servers) are still routed to the `SovereignContentGenerator`.
5. **Rebuild Package**: Run `npm run build` in `packages/core` or the root to apply changes.
6. **Verification**: Execute a command using the local model that triggers a web-fetch tool call and verify it routes correctly without OOMing the local server.

## Pitfalls and Fixes
- **OOM on local model**: If the local model tries to process the raw HTML directly, it may crash. **Fix**: Ensure the utility route handles the heavy lifting and returns only the cleaned/summarized text to the local model.
- **Quota errors on cloud**: Web scraping many pages can still hit Flash limits. **Fix**: Use `web-fetch-fallback` aliases to cycle through multiple API keys or models.

## Verification
- Run: `npm run start -- -m openai/gemma-4-26b-it -p "Summarize https://example.com"`
- Check logs for "SOVEREIGN_DEBUG" or equivalent tracing to confirm `gemini-3-flash-preview` was used for the fetch.
