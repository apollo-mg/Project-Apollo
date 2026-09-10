# "TURBO reduces thinking tokens by 1/2 to 1/10" — not reproduced; it thinks MORE on 4 of 5

**2026-09-02.** `.194`, 4x P100 sm_60 @ 150 W, 2 devices, `-c 16384 -ngl 99 -fa on -sm tensor`.
Thinking-mode sampling per the model card (identical to Unsloth's): `temperature=1.0, top_p=0.95,
top_k=20, min_p=0.0, presence_penalty=0.0`, `max_tokens=4096`. Predictions registered before the
run in `PREDICTIONS_turbo_thinking.md`.

| arm | model |
|---|---|
| turbo | `DavidAU/Qwen3.8-27B-TURBO-...-NEO-CODER-MAX-MTP-Q4_K_S` (16.33 GiB, `qwen35`, `nextn_predict_layers=1`, block_count 65 — MTP inline) |
| control | `Qwen3.8-27B-Q6_K` — the model `.73` serves in production |

## The claim

Card: *"TURBO: drastically reduces thinking tokens (by 1/2 to as high as 1/10) while maintaining
output quality."*

This was worth testing because today's measurements make token count the dominant term:
wall-clock per task = **tokens x (1/throughput)**. A day of tuning bought Flash-Next +20 %
throughput; halving thinking tokens on the 27B would save ~17 min/task at `.73`'s 22.6 tok/s.

## Result — reasoning_content length per prompt

| prompt | turbo | control | ratio |
|---|---|---|---|
| factual | 802 | 456 | **1.76x MORE** |
| arithmetic | 830 | 426 | **1.95x MORE** |
| logic puzzle | 2,630 | 1,141 | **2.30x MORE** |
| format (3 bullets) | 1,964 | 1,103 | **1.78x MORE** |
| no-repeat | 1,569 | 5,312 | 0.30x less |
| **total** | **7,795** | **8,438** | **0.92x** |

**The aggregate 0.92x is an artifact of one prompt.** On four of five, TURBO produced roughly
twice the thinking of the stock model. The single reduction comes from a prompt where the
*control* emitted a 5,312-character outlier — remove it and TURBO is 6,226 vs 3,126, i.e. **2.0x
MORE thinking**.

Claimed range 0.5x–0.1x. Measured 0.92x aggregate, ~1.9x median in the wrong direction.

## Quality is fine — this is not a broken model

Both answered all 5 prompts, all `finish=stop`, no truncation, no repetition. Arithmetic: both set
up `60(t+2) = 90t` correctly. Format compliance: both produced exactly three capitalised
single-sentence bullets. TURBO's answers are marginally longer overall (2,828 vs 2,506 chars).

Nothing here suggests the merge or the Heretic ablation damaged it. The specific headline claim
simply does not reproduce.

## Prediction scoring

| # | claim | conf | outcome |
|---|---|---|---|
| P1 | loads, answers all 5 | 0.85 | ✅ |
| P2 | thinking measurably lower | **0.55** | ❌ — higher on 4/5 |
| P3 | reaches the claimed >= 2x reduction | 0.30 | ❌ |
| P4 | reaches 10x on any prompt | 0.10 | ❌ |
| P5 | correctness holds | 0.60 | ✅ |
| **P6** | **some degradation visible** | **0.65** | **❌ — none observed** |

P6 was wrong in the model's favour. I expected a merge plus de-censoring ablation to show visible
cost, primed by the card's large claimed ARC gains (0.591 -> 0.735). No degradation appeared on
these five prompts. That is worth stating as plainly as the negative result on P2.

## Limits — and the test that would actually isolate TURBO

- 5 prompts, **K=1**. Existence proof, not a rate. Thinking length is high-variance: the control's
  own 5,312-char outlier on one prompt is the whole aggregate difference.
- **Quant differs** (Q4_K_S vs Q6_K). Should barely affect thinking *length*, which is behavioural,
  but it is unmatched.
- **This compares "DavidAU's merge" against "stock Qwen3.8-27B", not "TURBO" against "no TURBO".**
  Isolating the TURBO treatment needs DavidAU's non-TURBO build of the *same* merge. Without that,
  a null result cannot distinguish "TURBO does nothing" from "TURBO helps but the merge costs more
  than TURBO saves."

That third point is the one that matters, and it is the obvious follow-up if the claim is worth
chasing further.

---

**Follow-up 2026-09-03:** re-run at `reasoning_effort: medium` (no injected effort
instruction) in [RESULT_TURBO_THINKING_MEDIUM.md](RESULT_TURBO_THINKING_MEDIUM.md). The xhigh
aggregate of 0.92x was an artifact of a single control outlier; at medium TURBO thinks **more on
5/5 prompts, 2.52x aggregate / 2.15x median**, and drop-one-out never falls below 2.03x. The
injection was masking the effect, not creating it. The merge-vs-stock confound below still stands.
