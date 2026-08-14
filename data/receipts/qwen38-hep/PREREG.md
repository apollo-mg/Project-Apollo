# PREREG — Qwen 3.8 27B, HumanEval+ K=3: does thinking pay more at 2-bit than 6-bit?

**Sealed 2026-08-14 before any run.** Supersedes the saturated trivia 2x2 in
`data/receipts/qwen38-lowbit/`, which scored 8/8 in all four cells and could not have
measured a gap of any size.

## The question

`battle16gb/PUZZLE_LADDER_FA_ON.md`, on Nemotron-Puzzle-75B-A9B, HumanEval+ K=3:

| cell | pass@1 |
|---|---|
| q2_off | 67.5 % |
| q2_on | 92.5 % |
| iq4_off | 91.1 % |
| iq4_on | 94.3 % |

**Thinking gap 25.0 pp at Q2 -> 3.3 pp at IQ4.** Reading: reasoning tokens and weight
precision are substitutes. One model, one architecture. Qwen 3.8 27B is an independent
test — different vendor, different generation, **dense** rather than MoE.

## Why these two quants, and not the two already run

The trivia 2x2 used `UD-IQ2_M` and `UD-IQ3_XXS` — adjacent tiers. Puzzle's 25 pp gap was
**Q2 vs IQ4**, a much wider span. Adjacent quants plus a saturating prompt set is why that
run produced four identical cells. This ladder widens the precision axis to roughly match
Puzzle's:

| cell | file | size | notes |
|---|---|---|---|
| lo | `Qwen3.8-27B-UD-IQ2_M.gguf` | 9.61 GiB | carries **96 `IQ1_M` tensors**, a tier below its label |
| hi | `Qwen3.8-27B-Q6_K.gguf` | 21.31 GiB | `Q6_K` 361 + `Q8_0` 49 — also not uniform |

x {thinking on, thinking off} = 4 cells, 164 problems, **K=3 = 492 samples/cell**.

## Hardware: both cells on `.194`, deliberately

Both files fit **fully in VRAM** on 4x Tesla P100 (64 GiB total), so no offload and no
placement difference between cells. Running `IQ2_M` on the RX 9070 XT and `Q6_K` on `.194`
would have been cheaper in wall-clock but introduces a **backend confound**: different
kernels, different accumulation order, different arithmetic.

That is not a hypothetical concern on this fleet. `FA_EQUIVALENCE_SM60` measured `-fa on`
vs `-fa off` on this exact hardware at median KLD **0.000317**, same-top **98.686 %** —
roughly 1 token in 76 changing argmax from a *flag*. A cross-architecture split would be a
larger perturbation than that, and would make any observed gap unattributable.

Fleet state to record with the run: **150 W / 1063 MHz**, the standing config since
2026-07-17 (`gpu-clock-benchmark-discipline`).

## Harness

`data/receipts/humaneval-plus/hep_eval.py` — **the same instrument that produced the Puzzle
numbers**. Using a different benchmark would make the comparison cross-instrument and
worthless for this question.

Two properties of that harness matter here, both already present:

- It extracts answers from `content` **then** `reasoning_content`, so it does not repeat
  the defect found in the trivia runner, which captured only `content` and was blind to
  whether thinking fired at all.
- It records `rc_chars` per sample — reasoning-content length — which is the direct
  engagement check. A "thinking on" cell with zero `rc_chars` is void, not a result.

Settings: temp 0.7 / top_p 0.95 / top_k 20 (Puzzle's), `HEP_K=3`, thinking toggled via
`HEP_THINK`, which sets `chat_template_kwargs {"enable_thinking": false}`.

**`reasoning_effort` is deliberately left at default** in every cell. Measured today: the
default, `xhigh` and `high` are byte-identical, while `medium` and `low` differ
inconsistently by prompt. It is a live variable and does not belong in this experiment.

## Predictions, sealed

| # | prediction | conf |
|---|---|---|
| P1 | The thinking gap is larger at IQ2_M than at Q6_K (same direction as Puzzle) | 0.65 |
| P2 | The IQ2_M gap is smaller than Puzzle's 25.0 pp | 0.70 |
| P3 | Q6_K thinking-on scores >= 90 % pass@1 | 0.60 |
| P4 | IQ2_M thinking-off shows a higher TRUNCATED/NO_ANSWER rate than Q6_K thinking-off | 0.55 |
| P5 | All four cells score above the 67.5 % that Puzzle's q2_off produced | 0.60 |

P4 is the stopping-rule prediction and the one that matters most for interpretation.
`battle16gb` Finding 5 records a panel misattributing **cap-deaths** to silent closure
because `lm-eval` never recorded `finish_reason`. This harness buckets
PASS/WRONG/TRUNCATED/NO_ANSWER, so any gap gets decomposed rather than assumed.

## What would falsify the substitution hypothesis

If the thinking gap at IQ2_M is **not larger** than at Q6_K — or if both are inside the
~2 pp noise floor pre-registered for K=3 on 164 problems — then the Puzzle result does not
generalise beyond that model and should be restated as a property of
Nemotron-Puzzle-75B-A9B rather than of low-bit quantisation.

## Known limits before starting

- **Two quants is a two-point line.** It cannot distinguish gradual decay from a cliff.
  A third rung (`IQ4_XS`, 14.63 GiB) is the obvious extension if the two-point result is
  interesting.
- Both files are **unsloth dynamic recipes with non-uniform tensor mixes**, so this
  compares two files, not two clean bit-depths. `UD-IQ2_M` contains `IQ1_M` tensors;
  `Q6_K` contains `Q8_0` tensors.
- HumanEval+ is single-turn codegen. It does not measure the multi-turn tool-calling
  regime where this fleet's quantised models have historically actually broken
  (`loop-detector`, `hermesagent20`).
- Expected wall clock is long. Puzzle's 4-cell K=3 ladder took **36.4 h** on this node for
  a 75B-A9B; a dense 27B should be faster per token but this is still a multi-hour run.
