# Pre-registered — does DavidAU's "TURBO" actually cut thinking tokens?

Registered **2026-09-02**, before the model finished downloading.

## The claim being tested

`DavidAU/Qwen3.8-27B-TURBO-...-MTP-GGUF` card: *"TURBO: drastically reduces thinking tokens (by
1/2 to as high as 1/10) while maintaining output quality."*

This matters more than anything else measured today. Wall-clock per task is
**tokens x (1 / throughput)**, and today's numbers say the token count is the larger lever:
a day of tuning bought Flash-Next +20 % throughput, while model choice was worth 2.4x.
At `.73`'s 22.6 tok/s and ~47k tokens/task, halving thinking tokens saves ~17 minutes per task.

## Arms

| arm | model |
|---|---|
| turbo | `...NEO-CODER-MAX-MTP-Q4_K_S.gguf` (16.33 GiB) |
| control | `Qwen3.8-27B-Q6_K` — the model `.73` actually serves |

Same 5 prompts as the REAM trial, same sampling (thinking mode: `temperature=1.0, top_p=0.95,
top_k=20, min_p=0.0, presence_penalty=0.0`), `max_tokens=4096`.

**Primary metric: `reasoning_content` length per prompt.** Secondary: does `content` still answer
correctly, and does answer quality survive.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | loads and answers all 5 prompts | 0.85 |
| P2 | thinking tokens **measurably lower** than control | **0.55** |
| P3 | reduction reaches the claimed **>= 2x** | **0.30** |
| P4 | reduction reaches the claimed 10x on any prompt | 0.10 |
| P5 | answer correctness holds on the factual + arithmetic prompts | 0.60 |
| P6 | some degradation visible vs control (repetition, format misses, wrong answers) | 0.65 |

## Reasoning

**P2 only 0.55.** Thinking length is a learned behaviour; a merge plus Heretic ablation can shift
it in either direction, and today's REAM result is a live example of a modification that made
thinking *explode* rather than shrink. Claimed-by-the-author is weak evidence.

**P3 at 0.30, P4 at 0.10.** "1/2 to 1/10" is a wide, unfalsifiable-sounding range. Even a real
effect is unlikely to hit the top of it consistently.

**P6 at 0.65** because the card's own benchmark table claims ARC-C 0.591 -> 0.735 and ARC-E
0.782 -> 0.882 from a merge plus de-censoring ablation. Ablation normally *costs* capability. A
24 % relative ARC-C gain is large enough that the burden of proof sits with the claim.

## Confounds, stated up front

- **Quant differs**: Q4_K_S vs the control's Q6_K. Should barely affect thinking *length* (a
  behavioural property) but does affect quality, so P5/P6 are partly confounded.
- Different base merge, so any difference is "this model vs stock", not "TURBO vs no-TURBO".
  Isolating TURBO would need DavidAU's non-TURBO build of the same merge.
- K=1, 5 prompts. Existence proof only.

## Falsifier

If thinking length matches or exceeds the control, the TURBO claim is not reproduced on these
prompts and should be reported as such.
