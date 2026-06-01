name: benchlocal-integration
description: Integration strategy for BenchLocal (stevibe) for automated LLM benchmarking.

## Overview
BenchLocal is a local-first Electron/TypeScript application designed for standardized LLM benchmarking using installable "Bench Packs" (e.g., ToolCall-15, CLI-40).

## Key Features for Apollo
1.  **Bench Packs:** Standardized, repeatable test suites that replace anecdotal vibe checks with hard data.
2.  **Programmatic API:** Exposes a local API (OpenAPI/MCP) that allows AI agents to trigger benchmarks autonomously.
3.  **Local Execution:** Perfect for testing local inference engines (like llama-server running on the P100 or 9070 XT).

## Integration Strategy
- Use BenchLocal to construct a formal Model Lab workflow.
- Instead of manually sending curl requests to calculate TPS or check for hallucination loops (like the verify ubatch collapse in Buun's fork), configure BenchLocal to target the P100 and 9070 XT endpoints.
- Have the Daydream Daemon or Scientist use the BenchLocal API to automatically run ToolCall-15 overnight against new model quantizations (like APEX or TurboQuant).
