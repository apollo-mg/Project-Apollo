# PREREG: does the sub-3-bit quality drop show up in AGENTIC work?

**Written 2026-09-09 before the runs.** Predictions logged with confidence; scored honestly after.

## The gap this fills

ISTA's published curve (`reference/ISTA_GSQ_RCO_BASELINES.md`) measures **AIME25, GPQA-Diamond,
LiveCodeBench v6** — all **single-turn**. It shows a sharp knee at 3.0 bpw: 91.2 at IQ3_XXS against a
91.87 base, 89.6 at IQ2_S, 86.0 at IQ2_XS.

**Nobody in that comparison tested multi-turn agentic tool use.** Our TURBO result suggests the floor
behaves differently there — a model can hold single-turn quality and still fail to terminate on
"read the tail of a file." This measures the axis their charts do not.

## Design

| arm | model | GiB | isolates |
|---|---|---|---|
| A | `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` | 9.73 | 3-bit baseline |
| B | `Qwen3.8-27B-GSQ-RCO-IQ2_XS-mtp` | 8.17 | **bit depth alone** |

Same base model, same quant family, same MTP head, same everything except bit-width.
`-c 32768 -np 1 -fa on --kv-unified -ctk vbr -ctv vbr --vbr-floor t2 --vbr-vram auto`, **no
`--spec-type`**, fixed grader, fresh server per arm.

**The baseline is re-measured rather than reused.** det02 scored 0.943 but ran *with* MTP and hit the
acceptance collapse partway through. Comparing a 2-bit MTP-off run against a 3-bit MTP-on-degraded
run would confound quantisation with the defect found on 2026-09-08. Costs ~40 min, removes the
objection entirely.

## Predictions

- **P1: arm A (3-bit) completes 61 tasks without a contiguous wall.** 70%. MTP-off removed VBR
  clamping in the TURBO run (watermark flat at 13,312 vs the 21,504 trigger), which suggests the
  draft head was contributing most of the checkpoint pressure.
- **P2: arm B (2-bit) shows a LARGER agentic drop than the 5.9-point single-turn drop ISTA measured
  at this bit-width.** 65%. Multi-turn work compounds errors across turns and adds a stopping-rule
  requirement that single-turn benchmarks never test.
- **P3: arm B's failures are dominated by non-termination, not wrong answers.** 60%. That is the
  shape TURBO showed at 2-bit (bimodal: ~100 tokens or ~8,300), and it is a different failure mode
  from "gets the answer wrong."
- **P4: arm B still completes the corpus** (fails tasks but does not wall). 45% — genuinely
  uncertain. TURBO walled at 2-bit, but TURBO was also a merge; GSQ-RCO IQ2_XS is the strongest
  2-bit recipe by ISTA's own numbers.

## What would falsify the premise

If arm B's `valid_pass_rate` drop is close to ISTA's 5.9-point single-turn drop, then single-turn
curves **do** predict agentic degradation, and the extra measurement is unnecessary. That would be a
useful negative result and is explicitly worth reporting.

## Known limits

- K=1 per arm. Existence proof, not a rate.
- 61 tasks, one corpus, one hardware target.
- The verdict schema still collapses INFRA/FAIL — report all three counts separately, never a single
  rate (see `RESULT_TURBO_IQ2M_WALLED.md`, where 6/6 INFRA produced a flattering 1.000).

---

## PROTOCOL CHANGE (2026-09-09, mid-experiment): server-side `-n 4096` added

**First attempt abandoned at 17/61.** Arm A produced `PASS 8 / INFRA_ERROR 9` — a 53% timeout rate —
and `valid_pass_rate 8/8 = 1.000`, the same hollowed-denominator artifact this campaign keeps hitting.

**Cause:** `RESULT_RUNAWAY_ROOT_CAUSE.md`. Every task declares `max_tokens: 4096`; hermesbench parses
it and never sends it; llama-server's `--predict` defaults to **-1 (infinity)**. Measured on the
abandoned arm: **9 of 16 requests (56%) exceeded 4096**, max 9,379. The run was measuring the harness
defect, not bit depth.

**Change:** both arms relaunched with `-n 4096` on the server, which enforces exactly the budget the
corpus already declares. Nothing else changed.

**Why this is a fix and not a thumb on the scale:** it applies the corpus's own stated budget, equally
to both arms, and converts unmeasurable `INFRA_ERROR` timeouts into graded outcomes. Without it the
comparison measures how often each model hits a non-terminating task — a real property, but not the
one this prereg asks about.

**The abandoned run is kept** as `results/bitdepth_iq3xxs_NOBUDGET` — it is direct evidence of the
unenforced-budget defect reported in am423 issue #5.

**New run ids:** `bitdepth_iq3xxs_budget`, `bitdepth_iq2xs_budget`.

**Prediction added before relaunch — P5: the budget cap cuts INFRA_ERROR by more than half in arm A**
(from 53% to under 25%). 75%. If it does not, timeouts have a second cause beyond unbounded
generation.
