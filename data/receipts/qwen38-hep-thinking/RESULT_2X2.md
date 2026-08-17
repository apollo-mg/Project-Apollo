# Thinking substitutes for precision — a clean 2x2 on Qwen3.8-27B / HumanEval+

**2026-08-17**, `.194`, quad Tesla P100 (sm_60), 1063 MHz / 150 W.
Build `moe-cache-cuda` @ `bb3c3fa` (`giveen/moe-cache`), `-ngl 999 -c 20000 -fa on -np 1`,
**KV f16+f16** (no `-ctk`/`-ctv`). Harness `~/hep/hep_eval.py`, HumanEval+ **full N=164**,
temp 0.7 / top_p 0.95 / top_k 20, **K=3** (492 samples/cell). Results in
`~/qwen38_hep/*.json` on `.194`.

**Predictions were pre-registered in `PREDICTION_Q6K_THINKOFF.md` (commit `b7e203d`)** while
the final cell was at 18/164, with a scoring rule fixed in advance.

## The 2x2

| | thinking OFF | thinking ON | **thinking Δ** |
|---|---|---|---|
| **IQ2_M** | 88.21 % | 92.68 % | **+4.47 pp** |
| **Q6_K** | **92.07 %** | 93.90 % | **+1.83 pp** |
| **quant Δ** | **3.86 pp** | **1.22 pp** | |

Per-sweep spread (K=3): 0.76 / 0.50 / 0.86 / 0.50 pp respectively.

## The finding

**The quantisation gap triples when thinking is removed** — 1.22 pp with thinking, 3.86 pp
without. Equivalently, thinking is worth **2.4x more** to the 2-bit model than to the 6-bit
one (+4.47 vs +1.83 pp).

This is an **interaction**, not two independent main effects. Reasoning and weight precision
are partially substitutable: given room to think, a heavily-quantised model recovers most of
what quantisation cost it.

At a per-sweep sigma of 0.50–0.86 pp, the 2.64 pp difference between the two quant gaps is
roughly 3–5 sigma. Resolvable, not suggestive.

## Predictions, scored against the rule fixed in advance

| prediction | conf | outcome |
|---|---|---|
| **Primary:** thinking-OFF quant gap exceeds the thinking-ON gap of 1.22 pp (i.e. Q6_K OFF > 89.43 %) | **0.65** | **CONFIRMED** — 92.07 %, gap 3.86 pp |
| **Point estimate:** Q6_K OFF lands 90–92 % | 0.50 | **essentially correct** — 92.07 %, 0.07 pp above the band |

Scoring rule, fixed in advance: **CONFIRMED** ≥ 90.0 %, **UNRESOLVED** 89.0–90.0 %,
**FALSIFIED** < 89.0 %. Observed **92.07 %** → **CONFIRMED**, and not marginally.

The pre-registered worry — that HumanEval+ saturation would compress the effect below
resolution — did not materialise. It compressed the *magnitude* (this is 3.86 pp where
`PUZZLE_LADDER_FA_ON` saw 25.0 → 3.3 pp on a harder panel) but not below the noise floor.

## Instrument validity

The factor separated perfectly, which is the failure mode that kills experiments like this:

| cell | `enable_thinking` | thinking fired | mean reasoning chars | median out_tok |
|---|---|---:|---:|---:|
| IQ2_M OFF | `false` | **0 / 492** | 0 | 192 |
| IQ2_M ON | `true` | **492 / 492** | 7012 | 696 |
| Q6_K OFF | `false` | **0 / 492** | 0 | — |
| Q6_K ON | `true` | **492 / 492** | 4960 | 561 |

`enable_thinking:false` **is still honored** by the Qwen3.8 template even though the reasoning
dial moved to `reasoning_effort` (8 template sites vs 4). Had it been inert the 2x2 would have
silently collapsed into two duplicated arms and read as a clean null — the same shape as
`qwen38-lowbit/RESULT_2x2.md`, where all four cells saturated at 8/8.

**Zero truncations** across all 492 Q6_K-OFF samples, so no completion-budget artefact.

## Consistency, which the pooled number hides

Q6_K OFF: **147/164 solved every time, 8 never, 9 flaky** (sampling-sensitive at temp 0.7).
The 39 failing samples are concentrated in 17 problems, not spread thin — consistent with the
`PUZZLE_HUMANEVALPLUS` finding that these gaps are **stopping-rule failures**, not
answering failures.

## What this does NOT establish

- **One bench, one model family, one node.** HumanEval+ is short-form code with executable
  ground truth — the friendliest possible case for a no-thinking arm. A reasoning-heavy bench
  would likely show a larger thinking effect and possibly a larger quant gap.
- **`-fa on` in every cell.** `battle16gb/FA_EQUIVALENCE_SM60.md` measured `-fa on` as
  costing more fidelity than BF16→Q8_0 on sm_60. Constant across the 2x2 so the *contrasts*
  hold, but the absolute numbers carry that tax and are not comparable to any `-fa off` arm.
- **`cache_prompt` at its default `true`**, and all 164 problems share an instruction
  preamble, so the three sweeps are not strictly independent draws. Weak at temp 0.7 with
  K=3, but real. Backlog **B1**.
- **Not a token-budget-matched comparison.** The thinking arms spend ~3.6x more output tokens
  (696 vs 192 median at IQ2_M). "Thinking helps" here means "helps per *problem*", not "per
  token". A token-matched design would ask a different and also interesting question.
- **KV was f16 throughout**, so none of the day's KV findings touch these numbers.

## Cost

15,391 s (4.3 h) for the final cell. Decode ran at **7.8 t/s** under default layer split;
`qwen38-splitmode/RESULT_P100_SM_TENSOR.md` puts `-sm tensor` at 1.62x. Deliberately not
changed mid-ladder — three cells were already banked under layer split, and comparability was
worth more than the hour. **That 1.62x belongs to the next ladder, set at the start.**
