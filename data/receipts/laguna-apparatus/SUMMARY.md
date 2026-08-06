# The apparatus arm — attaching an agent prompt costs 18.9 points of *score* and ~0 points of *capability*

**Date:** 2026-07-27 (run started 2026-07-26 18:48 UTC, elapsed **58,300 s / 16.2 h**)
**Model:** `Laguna-S-2.1-UD-Q2_K_XL`
**Hardware:** `.194`, 4× Tesla P100 (sm_60), **1063 MHz / 150 W**
**Server:** `-c 32768 -np 1 -ngl 99 -sm layer -ts 1,1,1,1 -fit off`
**Eval:** HumanEval+ full 164 × K=3 = 492 samples, t0.7 / top_p 0.95 / top_k 20,
max_tokens 16000, thinking at template default

## Why this run exists

Every arm in the offlabel#10 discussion sits at the **no-apparatus** end — bare user
message, no system prompt, no tools. So "regime" (single-turn codegen vs long agentic) and
"apparatus dose" (system prompt + tool schemas) were **perfectly confounded**. Nobody had
run codegen *with* a full agent prompt attached.

This is that cell at full scale. **Every parameter is identical to the 90.85% baseline**
(`laguna_hep_results_t07_k3.json`) except the apparatus: a 752-byte agent system prompt
and 3 tool schemas, both saved verbatim alongside this file (`agent_prompt_used.txt`,
`agent_tools_used.json`) so the cell is replicable exactly.

## Headline — and why the headline is misleading

```
PASS=354  WRONG=31  TRUNCATED=1  TOOL_CALL=106  NO_ANSWER=0  EXEC_TIMEOUT=0
pooled pass@1 = 71.95%   (354/492)
per-sweep     = 71.95% ± 1.49%  (K=3 virtual sweeps; min 70.1%, max 73.8%)
```

| | baseline (no apparatus) | apparatus arm | delta |
|---|---|---|---|
| pass@1 | **90.85 %** | **71.95 %** | **−18.90** |
| **WRONG** | **30** | **31** | **+1** |
| TOOL_CALL | 0 | **106** | +106 |
| no extractable answer | 11 | **0** | −11 |
| cap-hits / TRUNCATED | 12 | **1** | −11 |
| flaky problems | 11 / 164 | 73 / 164 | +62 |
| solved 3/3 | 143 / 164 | 78 / 164 | −65 |

**The WRONG count is 31 against 30.** The apparatus did not degrade the model's ability to
answer. It changed what the model *does*: 106 of 492 samples (21.5%) are the model calling
a tool instead of emitting code, which a single-turn codegen harness scores as failure.

**Conditional on attempting an answer:**

> **354 / 386 = 91.71 %**, against the 90.85 % baseline.

Indistinguishable — marginally higher, well inside the ±1.49% per-sweep spread.

## Three findings

### 1. Apparatus costs score, not capability

18.9 points of measured pass@1, ~0 points of answering ability. Any benchmark that scores
a tool call as a wrong answer will systematically **understate agent-configured models**,
and the size of the understatement here is large enough to invert conclusions.

### 2. The apparatus *eliminated* the termination failures

No-extractable went **11 → 0**; cap-hits **12 → 1**.

Those 11 samples were the **entire** ON-vs-OFF gap in the original finding — the basis for
"it does not fail to reason, it fails to give up." Give the model tools and that failure
mode disappears, presumably because an uncertain model routes to a tool instead of looping.

This is worth weighing against the loop-detector work: a stopping rule is one fix for
degeneration, and **having somewhere to route** appears to be another.

### 3. The flakiness explosion is tool-routing variance, not answer variance

Flaky problems 11 → 73. The bucket patterns show why: `T,P,P`, `P,T,P`, `T,T,P` — same
problem, same settings, sometimes a tool call and sometimes an answer. It is not that
answers became unstable; it is that the **route** became unstable.

Same stochasticity family as the temperature-0 bimodality measured on `.73`
(`data/receipts/hermesagent20/`), surfacing in a different place.

## What this does to the regime-vs-apparatus question

It **de-confounds** them. Apparatus dose alone, holding regime fixed at single-turn
codegen, moves measured score by −18.9 points while leaving capability flat. So a
comparison between a no-apparatus codegen run and an apparatus-bearing agentic run cannot
attribute its difference to *regime* — apparatus alone accounts for a swing of that
magnitude.

Corollary that contradicts the public read: **"coding-shaped tasks suppress thinking" is
not supported here.** Thinking fired on **445/492 samples (90.4%)**, mean
`reasoning_content` 4,686 chars, in the most coding-shaped cell we have.

## Scope limits

- **Tools were passed but never called back.** No tool output re-entered the context. A
  real agent loop feeds results back every turn; that is untested and plausibly a stronger
  variable than schema presence alone.
- **One quant** (Q2_K_XL), one model, one prompt. The 752-byte prompt is one point in a
  large space — a different agent prompt could route more or less aggressively.
- **The 2×2 predicted a stronger thinking suppression than appeared here.** That K=1
  15-problem cell showed persona+tools firing on only 13/15 with 0.39× reasoning length.
  At n=492 thinking fired 90.4% of the time. The suppression effect is real but **much
  weaker at scale than the 2×2 implied** — treat the 2×2 as an effect-sizing exercise that
  overstated it.

## Raw

- `laguna_hep_results_t07_k3_agentprompt.json` — 164 problems, per-sample buckets, token counts
- `laguna_hep_t07_k3_agentprompt.log` — full per-problem run log
- `agent_prompt_used.txt` (752 B) / `agent_tools_used.json` (3 schemas) — verbatim, for replication
- `agent_prompt_arm.log` — driver log with clock state
