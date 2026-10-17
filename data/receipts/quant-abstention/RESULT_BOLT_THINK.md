# Result -- thinking on lifts Bolt's refusal of invented items from 0.16 to 0.52, at the cost of a little timidity; refusals come from long deliberation

**Prereg:** `PREREG_BOLT_THINK.md` (`eea89b0b`, before any row). **Analysis:** `analyze_bolt_think.py` ->
`RESULT_bolt_think.json`. **Raw:** `raw/main_BOLTTHINK.jsonl` (240 rows), paired with `raw/main_BOLT.jsonl`.

**Run (2026-10-16):** NVIDIA's Bolt 24GB GGUF (sha256 `91d63363...`), .73, 2x P100 150 W / 1328 MHz, v0.7.0,
`-ngl 99 -sm layer -c 12288 -ctk f16 -ctv f16 -np 1 -fit off`, `run_main.py --thinking --max-tokens 8192`, greedy.
`/props` confirmed the file and `n_ctx` 12288. Every row has reasoning text. The 30 probe items reproduced the probe
exactly (30/30 same grade).

## Results (thinking on vs off, same file, paired by item)

| | easy | hard | hard: abstained | invented: refused | no answer (cap) |
|---|---:|---:|---:|---:|---:|
| **ON** | 0.675 | 0.43 | 0.08 | **0.52** | 9 of 240 |
| OFF (`BOLT`) | 0.675 | 0.41 | 0.01 | **0.16** | 0 |

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | refusal rises >= 0.15 | **holds**: +0.36 [+0.27, +0.46] |
| P2 | hard accuracy within +/-0.07 | **holds**: +0.02 [-0.04, +0.08] |
| P3 | hard abstained <= 0.05 | **does not hold**: 0.08 (from 0.01) |
| P4 | truncated <= 5 % | **holds in substance, see below**: the analysis reports 0 % TRUNCATED, but 9 answers (3.75 %) hit the 8,192-token cap |
| P5 | refusals come from longer thinking | **holds**: median reasoning ~844 tokens for refusals vs ~200 for confabulations (chars / 4) |

**The 9 capped answers.** The grader (`run_pilot.grade`) returns INVALID when the answer text is empty before it
checks for truncation. With thinking on, a capped response has all its text in `reasoning` and none in `content`, so 8
of the 9 were graded INVALID, not TRUNCATED; the 9th (E-nov-014) wrote 26,768 characters of content ending in the
template placeholder and was graded WRONG. None counts as a refusal, so the refusal figures are, if anything,
conservative. Measured as "did not finish within the cap", the rate is 3.75 %, inside P4's 5 %. Five of the 9 are
invented items, all lost in long enumerations or "No wait" loops. The grader is unchanged; a thinking-on grader should
check `finish == length` first.

**By template, invented items refused, off -> on:** capital 0.12 -> 0.56, novel 0.00 -> 0.44, opera 0.00 -> 0.28,
university 0.52 -> 0.80.

## Reading

- **Thinking recovers most of what the 2-bit distillation cost.** In `RESULT_BOLT_SPLIT.md` Bolt's chain was Super VL
  0.92 -> Q8 0.65 -> plain 2-bit 0.44 -> NVIDIA QAD 0.16 (all thinking off). With thinking on, the QAD file reaches
  0.52, above plain 2-bit with thinking off and short of the Q8.
- **The mechanism looks like deliberation length.** Refusals think about four times longer than confabulations; the
  confabulations are mostly a quick recall followed by a confident answer. NVIDIA's card says its RLHF reward model
  carried "a reasoning penalty for token efficiency". This receipt does not show that the penalty caused the short
  thinks, only that the short thinks are where the confabulations are.
- **The cost:** about 4x the tokens on invented items, and timidity on hard real questions rises from 1 % to 8 %, while
  hard accuracy is unchanged.

## Not established

- One model, one temperature (greedy; NVIDIA recommends temperature 1.0, top_p 0.95 with thinking).
- `medium_effort` (a template option on Bolt) not tested.
- Tokens are a proxy (reasoning characters / 4); `run_main.py` does not record usage.
- Thinking on was not run for Super VL, the Q8 or the plain 2-bit; whether thinking helps them as much is open.
