---
name: configure-model-lab-benchmarking
description: Setup a localized, automated "Model Lab" to objectively evaluate LLMs using an LLM-as-a-Judge pipeline. Use when model "vibes" are inconsistent or when benchmarking new quantizations for agentic reliability.
---

# Configure Model Lab Benchmarking

## Overview

Academic benchmarks are poor predictors of agentic performance. The Model Lab creates a localized CI/CD pipeline that tests models against project-specific adversarial prompts and grades them using a high-fidelity "Judge" model.

## Workflow Decision Tree

1. **Test Phase:** A TypeScript runner (`apollo_lab.ts`) executes a "Golden Dataset" of prompts against a candidate model.
2. **Persistence Phase:** Raw JSON results (prompts, tool calls, responses) are saved to a `lab/results/` directory.
3. **Grading Phase:** A Python script (`judge.py`) feeds the results to a heavy model (e.g., Darwin-36B) which assigns scores based on a strict rubric.

## Step 1: Curate the Golden Dataset (`dataset.jsonl`)

Prompts should target known failure modes:
- **PTC Schema:** Test if the model follows Programmatic Tool Calling return shapes.
- **Negative Ops:** Ask to read a non-existent file to test hallucination.
- **Strict Constraints:** Ban specific libraries (e.g., "Do not use subprocess").

## Step 2: Implement the Evaluation Runner (`apollo_lab.ts`)

The runner must enforce strict determinism and timeouts.

```typescript
// Add to your orchestrator examples/ entry points
const runner = new AgentRunner(adapter, registry, executor, {
  model: profile.model,
  maxTurns: 5, 
  temperature: 0.6, // Variance required for distilled MoE "thinking" models
  topP: 0.95,
  contextStrategy: profile.context_strategy,
  // Enforce a hard timeout per test (e.g., 10 mins for P100 cluster)
  abortSignal: AbortSignal.timeout(600000)
})
```

## Step 3: Implement the LLM-as-a-Judge (`judge.py`)

The judge requires a scoring rubric and a JSON output format.

```python
JUDGE_SYSTEM_PROMPT = """You are an expert AI evaluator.
Grade the agent's raw output against the task requirements.
Output your evaluation in strict JSON:
{
  "score": <1-5>,
  "passed": <bool>,
  "reasoning": "<concise explanation>"
}
"""

def evaluate(result):
    # Call a heavy model (e.g., Q6/Q8 Darwin or Qwen)
    # Strip markdown backticks before json.loads()
    clean_content = raw_content.strip()
    if clean_content.startswith("```json"):
        clean_content = clean_content[7:-3]
    return json.loads(clean_content)
```

## Pitfalls & Calibration

- **MoE Sampling:** Never use `temperature: 0.0` for judging or running distilled MoE models (R1/Opus distillation). They will often return empty strings or enter infinite CoT loops. Use `0.4` - `0.6`.
- **Infrastructure:** Run the Candidate model and the Judge model on the same dual-node cluster (P100 + RX 9070 XT) for maximum throughput.
- **Connectivity:** Ensure `judge.py` defaults to the correct LAN IP (e.g., `10.0.0.71:8082`) if running in a distributed environment.
