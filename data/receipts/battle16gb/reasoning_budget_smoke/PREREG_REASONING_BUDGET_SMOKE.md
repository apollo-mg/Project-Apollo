# Prereg — is `--reasoning-budget` live on the Battle-for-16GB pair?

**Date:** 2026-08-08, logged before any inference. **Rig:** RX 9070 XT 16GB (gfx1201), stock
clocks — the same silicon as the panel. **Not `.73`**: both arms are HIP/ROCm builds and cannot
execute on P100s.

## Why this exists

`Battle16GB_Results.md` (2026-07-18) attributes the entire outcome to **answer-delivery
discipline under thinking templates**, not ability:

- **Bonsai-27B ternary** — 20.3 % IFEval empties, *confirmed 4096-cap deaths* from over-thinking.
- **Gemma-4-12B QAT** — 32.3 % IFEval empties, **zero** budget-cap hits; it closes reasoning and
  EOSes without emitting an answer. The results doc already names the missing arm:
  *"Follow-up candidate: rerun one Gemma leg with `enable_thinking:false`."*

`--reasoning-budget` caps the *thinking* segment specifically, leaving the rest of the 4096 gen
budget for the answer. That targets Bonsai's failure mode directly and hands Gemma the
`enable_thinking:false` arm for free.

**Framing, stated up front so the result reads honestly either way:** if the flag is live on
Bonsai the expected effect is to *convert cap-deaths into answers*, which **raises** Bonsai's
IFEval and **widens** the ternary win. A re-run is not a threat to the published headline — it is
the follow-up the results doc asked for. If the flag is inert, the panel stands as published and
no re-run is owed.

**This smoke test does not re-run the panel.** It answers one question: is the flag live, and is a
bounded budget expressible? The full panel is ~16.4 h and is not authorised by this leg.

## Design

Server-level flag (`LLAMA_ARG_THINK_BUDGET`), so one server launch per cell. Six cells:

| model | build | port | ctx | budgets |
|---|---|---|---|---|
| Bonsai-27B Q2_g64 (7.59 GB) | `engines/llama_cpp_bonsai/build_hip` | 8093 | 32768 | −1, 0, 1024 |
| Gemma-4-12B QAT UD-Q4_K_XL (6.72 GB) | `engines/llama_cpp_turboquant/build_rocm` | 8094 | 16384 | −1, 0, 1024 |

Both: `-ngl 99`, fp16 KV, fa on, `--jinja`, `--reasoning-format deepseek`, greedy (temp 0),
`max_tokens 2048`, 8 IFEval prompts (the 8 most-constrained of the panel's 541, selected
deterministically — deliberation is longest where constraints stack, which is where cap-deaths
were observed).

**Deviation from panel config, declared:** Gemma runs **MTP off**. The drafter accepts a variable
token count per step, which would make `completion_tokens` noisy for reasons unrelated to the
flag; the structural discriminator is template-level and drafter-independent, so nothing is lost.
A panel re-run would carry MTP, and any MTP×reasoning-budget interaction is a separate one-cell
check *after* the flag is known live. `max_tokens` is 2048 rather than the panel's 4096 — the
budget under test (1024) sits below it, so the mechanism is still exercised.

## Gates

- **G-RB0 (positive control, runs FIRST per model, hard gate).** At budget **−1**,
  `reasoning_content` must be non-empty on ≥ 4 of 8 prompts. If it is not, the template is not
  wired for thinking at all, budget-0 output is **uninterpretable** (absent reasoning from a
  silently-dropped thinking path is indistinguishable from a correctly honoured budget), and that
  model is **aborted, not recorded as "flag works."** This is the Akicou chat-template burn
  (G-1b, `PREREG_REAP_DOSE_RESPONSE.md` Amendment 1) in a new costume; it is gated, not assumed.
- **G-RB1.** Boot log captured per cell and grepped for template/reasoning capability.
- **G-RB2.** Serving cmdline + build id recorded per cell.

## Discriminators (runtime-readable)

1. **Structural** — `reasoning_content` non-empty at −1, empty at 0. Primary.
2. **Bounded** — at 1024, mean reasoning-token count ≤ ~1024 and strictly below the −1 mean.
   This is the one that decides whether the contemplated re-run is even expressible.
3. **Volume** — `completion_tokens` and `finish_reason` per response.

## Predictions (logged before any inference)

| id | prediction | conf |
|---|---|---|
| **P-RB1** | budget 0 is LIVE on **Gemma** (mainstream model, well-formed template) | 0.75 |
| **P-RB2** | budget 0 is LIVE on **Bonsai** | 0.50 |
| **P-RB3** | if live on Bonsai, mean completion_tokens at 0 drops ≥ 50 % vs −1 | 0.70 |
| **P-RB4** | positive budget (1024) is honoured as a *bound* on both models where 0 is live | 0.65 |

P-RB2 sits at 0.50 deliberately: Bonsai is a **third-party ternary requant** of a Qwen3.6-27B
backbone, and that is precisely the population where chat templates go missing — see
[[gguf-label-is-not-a-spec]] and the four Akicou GGUFs that shipped no `tokenizer.chat_template`
at all and voided a five-arm run.

**P-RB5 (panel-level, NOT scoreable by this test — logged, will remain unscored here):** a
re-run with a bounded budget raises Bonsai's IFEval prompt-strict above 73.0 % and leaves Gemma's
32.3 % empty rate substantially unchanged, because Gemma's failure is silent closure with *zero*
cap hits — a cap addresses a failure she does not have. Conf 0.80.

## Receipts

Written directly to `data/receipts/battle16gb/reasoning_budget_smoke/` as they are produced —
**not** via the scratchpad. The panel's own per-prompt results are gone because they lived in
`/tmp` (see [[scratchpad-is-volatile]]); that is not repeated here.
