---
name: implement-proactive-memory-consolidation
description: Procedural implementation of a biologically-inspired memory consolidation loop (Daydream Daemon) that reinforces relevant memories and prunes stale data using Ebbinghaus decay.
---

## When to Use
Use this skill when designing a long-term memory system for local agents that prevents vector database bloat, surfaces abstract connections between past conversations, and simulates "biological" retention of frequently used concepts.

## Procedure

### 1. Implement Idle Monitoring (The Trigger)
Create a background loop that monitors system utilization to ensure the consolidation process only runs when the system is not in use (e.g., while the user is away or the GPU is idle).
- **Metric**: Use Exponentially Weighted Moving Average (EWMA) for GPU utilization (see `implement-gpu-aware-idle-monitoring`).
- **Threshold**: Set a low threshold (e.g., < 15% GPU/CPU) for at least 5-10 minutes.
- **Safety**: Implement a "pause file" (e.g., `daydream_pause.lock`) that can be created by the user or other scripts to temporarily disable the daemon.

### 2. Associative Memory Sampling
Instead of linear scanning, use associative recall to find related memory fragments.
- **Seed**: Pick 1-2 random documents from the vector database (e.g., ChromaDB).
- **Cluster**: Query the database for 2-3 additional documents similar to the seed.
- **Context**: Package these fragments into a single prompt for the reasoning model.

### 3. Generate Epiphanies (The Reflection)
Use a high-reasoning model (e.g., Qwen 3.6 MoE or Gemma 4) with thinking blocks enabled to "daydream" about the fragments.
- **Prompt**: "You are the subconscious Default Mode Network. Review these fragments. Find a non-obvious connection, a lingering question, or a core principle we learned."
- **Output**: Force a JSON schema containing `epiphany` (the thought) and `actionable_insight` (a concrete takeaway).
- **Reinforcement**: For every document sampled, increment its `recall_count` and update its `last_accessed` timestamp in the database metadata.

### 4. Apply Biological Decay (The Sleep Cycle)
Implement a nightly pruning script (e.g., `prune_memories.py`) that applies the Ebbinghaus Forgetting Curve formula to all non-permanent memories.
- **Formula**: `Strength = importance * e^(-lambda_eff * days_old) * (1 + recall_count * 0.2)`
- **Variables**:
    - `importance`: Assigned during ingestion (0.1 for typos, 0.9 for architectural decisions).
    - `lambda_eff`: Decay constant (e.g., 0.05).
    - `recall_count`: Incremented by the Daydream Daemon or manual retrieval.
- **Pruning**: Delete documents where `Strength < threshold` (e.g., 0.1).

### 5. Integration with Live Agent
Inject the generated "Epiphanies" into the live agent's next "Tick" or initialization sequence so it can act on the new insights proactively.

## Pitfalls and Fixes
- **Symptom**: Important code snippets are being pruned.
  - **Cause**: The `importance` score was too low or the snippet hasn't been "daydreamed" about recently.
  - **Fix**: Implement a `permanent_fact` metadata tag or a "Hardware Lock" in the pruning script that bypasses the decay formula for specific memory types.
- **Symptom**: Daydreaming is interrupting user tasks (e.g., gaming).
  - **Cause**: Simple utilization thresholds are too sensitive.
  - **Fix**: Use EWMA for GPU monitoring and increase the idle duration requirement.

## Verification
- Run `daydream.py` and verify `recall_count` increments in the ChromaDB metadata after a successful sequence.
- Run `prune_memories.py --dry-run` and verify it identifies "stale" chat logs for deletion while preserving reinforced epiphanies.
- Check `data/weekly_epiphanies.jsonl` for high-signal insights that bridge different project modules.
