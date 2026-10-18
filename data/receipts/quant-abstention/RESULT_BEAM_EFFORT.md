# Result -- Beam's reasoning effort buys almost nothing on factual questions: every setting above minimal answers the same (easy 0.975, hard 0.88-0.89 vs 0.86) for 1.6-1.8x the output; minimal is the setting for lookups

**Prereg:** `PREREG_BEAM_EFFORT.md` (`3074cd77`, before any M1 row; sizing probe on non-M1 items first). Chain fix
`d7ae5de6` (`python3 -s`, before any row). **Analysis:** `analyze_beam_effort.py` -> `RESULT_beam_effort.json`.
**Raw:** `raw/main_BEAM{MAX,LOW,HIGH,MED}.jsonl` (240 rows each, `--usage`), stored minimal arm `raw/main_BEAM.jsonl`,
`raw/beam_effort_state.log`.

**Run (2026-10-17 17:39 -> 2026-10-18 18:04, unattended):** .194 4x P100 at 150 W / 1063 MHz, upstream llama.cpp
`f74e2fa6a`, AtomicChat `AD-IQ2_XXS` (133.8 GB), routed experts of the last 28 MoE layers on CPU, `-ts 8,6,6,33`,
`--no-op-offload`, `-c 24576`, fresh server per arm, client on .194, greedy, `max_tokens` 8192. 960 rows, every one
`finish: stop`: no answer ran away at any setting, including max.

## Results

| effort (budget) | easy | hard | invented refused | hard refused | median tokens | p90 | max | median s/answer | arm hours |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| minimal (8), stored | 0.975 | 0.86 | 0.98 | 0.02 | ~190* | | | | 3.5 |
| low (32) | 0.975 | 0.88 | **0.99** | 0.02 | 295 | 628 | 2,183 | 73 | 5.7 |
| medium (64) | 0.975 | **0.89** | 0.96 | 0.01 | 330 | 794 | 1,549 | 77 | 6.0 |
| high (128) | 0.975 | 0.88 | 0.94 | 0.01 | 326 | 884 | 2,741 | 78 | 6.6 |
| max (512, Beam's default) | 0.975 | 0.88 | 0.97 | 0.02 | 289 | 745 | 3,570 | 73 | 5.8 |

\*The minimal arm predates `--usage`: its median output is 690 characters; the new arms run 3.6 characters per token.

Against minimal (paired by item): hard +0.02 to +0.03 (max +0.02 [0.00, +0.05]; medium +0.03 [0.00, +0.07]);
invented refusal +0.01 (low) to -0.04 (high, [-0.10, +0.01]). Item-level changes are a handful either way (2-7 items).
Invented questions are the expensive ones at every setting: median 488-585 tokens, against 107-146 for easy ones.

## Registered verdicts

| # | prediction | outcome |
|---|---|---|
| P1 | every setting above minimal costs more per answer (>= 1.3x characters) | **holds**: 1.56x (max) to 1.82x (high) |
| P2 | above minimal, the setting barely moves cost (max / low in [0.67, 1.5]) | **holds**: 0.99 |
| P3 | the default (max) does not lose refusals | **holds**: -0.01 [-0.05, +0.03] |
| P4 | the default does not buy knowledge (\|hard diff\| <= 0.05) | **holds**: +0.02 [0.00, +0.05] |
| P5 | answers finish (<= 2 % unfinished) | **holds**: 0 % in every arm |

## Reading

- **For factual lookups, set Beam to minimal.** Low, medium, high and max are indistinguishable from each other on
  accuracy and from minimal within two or three hard questions in 100, and they cost 1.6-1.8x the output. On this fleet
  that is ~75 s per answer against ~50 s; on any hardware it is the same token ratio.
- **The budget scales with the task, not the setting.** On these short questions every setting above minimal spends
  roughly 300 tokens; the same max setting spent ~6,200 tokens per pelican (`svgbench-beam/RESULT_BEAM_PELICAN.md`).
- **Unlike the prior art, no runaway.** On Qwen3.8-27B, `xhigh` turned abstentions into non-termination
  (`viability/RESULT_EFFORT_SWEEP.md`); Beam's trained numeric budget finished every one of 960 answers.
- **More thinking did not sharpen calibration either.** Refusal of invented items stays 0.94-0.99 at every setting;
  high is the lowest and most expensive, within noise.

## Not established

- One task type (short factual recall with abstention); agentic or long-form tasks may reward effort differently.
- Greedy decoding only; one 2-bit quant; one instrument of 240 items.
