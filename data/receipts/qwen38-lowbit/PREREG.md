# PREREG — Qwen 3.8 27B at the low end: does the thinking/precision substitution replicate?

**Sealed 2026-08-14, before any run.** Model files downloading at write time.

## The claim under test

`data/receipts/battle16gb/PUZZLE_LADDER_FA_ON.md` found, on Nemotron-Puzzle-75B-A9B over
HumanEval+ at K=3:

| cell | pass@1 |
|---|---|
| q2_off | 67.5 % |
| q2_on | 92.5 % |
| iq4_off | 91.1 % |
| iq4_on | 94.3 % |

**Thinking gap 25.0 pp at Q2 -> 3.3 pp at IQ4.** Reading: reasoning tokens and weight
precision are substitutes — a Q2 model that thinks scores about what an IQ4 model that
does not.

That is **one model, one architecture, one benchmark**. Qwen 3.8 27B is an independent
test: different vendor, different generation, and **dense** rather than MoE (censused
today — `qwen35` arch, 65 blocks, 0 expert tensors).

## Why the low end first

The effect lives at low precision. At Q6 both arms score near ceiling and the comparison is
uninformative. `UD-IQ2_M` is also a *known-interesting* file from today's census: it carries
**96 `IQ1_M` tensors**, a full tier below its label, and `IQ1_M` is where degradation is
sharpest. `UD-IQ3_XXS` is the neighbour that isolates whether `IQ1_M` is the culprit.

Both fit the 16 GB RX 9070 XT fully resident (9.61 / 11.10 GiB), so there is no offload or
placement confound — unlike every MoE arm run this week.

## Predictions, with confidence, before any data

| # | prediction | conf |
|---|---|---|
| P1 | The thinking gap is larger at IQ2 than at IQ3 (same direction as Puzzle) | 0.70 |
| P2 | The IQ2 gap is smaller than Puzzle's 25.0 pp — a dense 27B is not a 75B-A9B | 0.60 |
| P3 | `UD-IQ2_M` thinking-off produces at least one loop or non-stop failure in 20 prompts | 0.55 |
| P4 | Failures at IQ2, if any, are **stopping-rule** (non-stop / cap-death), not wrong-answer | 0.65 |
| P5 | `UD-IQ3_XXS` thinking-on is within 5 pp of `UD-IQ2_M` thinking-on | 0.50 |

P4 is the one that matters most and is easiest to get wrong. `battle16gb` Finding 5 already
records a case where a panel misattributed **cap-deaths** to silent closure because
`lm-eval` never recorded `finish_reason`. Any failure here gets classified by reading the
actual stop reason, not by inferring it from a low score.

## Method

- **Hardware:** RX 9070 XT, 16 GB, control plane. Record clock/power state with the run
  (`gpu-clock-benchmark-discipline`).
- **Server:** `llama-server`, both models fully resident (`-ngl 999`), **no TurboQuant KV
  flags** — `-ctk q8_0 -ctv turbo4` is the tuned serving recipe but it is a separate
  variable and would confound a quant comparison. f16 KV both arms.
- **Arms:** 2x2 — {`UD-IQ2_M`, `UD-IQ3_XXS`} x {thinking on, thinking off} via
  `--chat-template-kwargs '{"enable_thinking": …}'`.
- **Prompts:** fixed set, identical across all four cells, run in identical order.
- **Recorded per response:** `finish_reason`, token count, wall time, and the raw text.
  A score without its stop reason is not a result.
- **Ordering:** arms reversed on a second pass. This week produced 3.9x (pp) and 2.0x (tg)
  swings on *identical configs* from blocked position alone; one ordering is not evidence.

## What would falsify the substitution hypothesis

If the thinking gap at IQ2 is **not** larger than at IQ3 — or if both are near zero — the
Puzzle result does not generalise beyond that model, and should be restated as a property
of Nemotron-Puzzle rather than of low-bit quantisation.

## Known limits before starting

- K=1 per cell to begin with. `agent-benchmark-determinism` records temp-0 runs on this
  fleet as non-reproducible (HA-04 was bistable 35/100/100/35), so a single pass is an
  existence proof, not a rate. Repeat counts get raised only for cells that look decisive.
- Two quants is a two-point line. It cannot distinguish linear degradation from a cliff.
- `UD-IQ2_M` and `UD-IQ3_XXS` are both **unsloth dynamic** recipes with different tensor
  mixes; this compares two files, not two clean bit-depths.
