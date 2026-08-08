# Result — the same flag does opposite things on the two arms; a bounded budget rescues both

**COMPLETE.** All 6 cells. Pre-registered in `PREREG_REASONING_BUDGET_SMOKE.md`, logged before
any inference.

**Date:** 2026-08-08. RX 9070 XT 16GB (gfx1201), stock clocks. Bonsai-27B Q2_g64 (7.59 GB) on
`engines/llama_cpp_bonsai/build_hip` `-c 32768`; Gemma-4-12B QAT UD-Q4_K_XL (6.72 GB) on
`engines/llama_cpp_turboquant/build_rocm` `-c 16384`, **MTP off** (declared deviation). Both
`-ngl 99 -fa on` fp16 KV, `--jinja --reasoning-format deepseek`, temp 0 / top_k 1,
`max_tokens 2048`, 8 most-constrained IFEval prompts of the panel's 541.

## Headline

| model | budget | w/reasoning | **w/answer** | mean reason ch | mean tok | cap | stop |
|---|---|---|---|---|---|---|---|
| **Bonsai** | −1 | 8/8 | **0/8** | 8263 | 2048 | 8 | 0 |
| **Bonsai** | **0** | 8/8 | **0/8** | 8263 | 2048 | 8 | 0 |
| **Bonsai** | **1024** | 8/8 | **8/8** | 4150 | 1617 | 3 | 5 |
| **Gemma** | −1 | 8/8 | **2/8** | 7806 | 2014 | 6 | 2 |
| **Gemma** | **0** | **0/8** | **8/8** | 0 | 518 | 1 | 7 |
| **Gemma** | **1024** | 8/8 | **8/8** | 4105 | 1321 | 0 | 8 |

```
answers delivered      -1        0       1024
  Bonsai              0/8      0/8       8/8
  Gemma               2/8      8/8       8/8
```

## Finding 1 — `--reasoning-budget 0` is model-dependent, and the template is the discriminator

- **Bonsai: INERT.** Budget-0 output is **byte-identical** to unrestricted — 0 differing fields
  across 8 responses × 11 fields, and identical generated text 8/8. The flag does nothing.
- **Gemma: LIVE.** 58 differing fields; reasoning collapses 8/8 → **0/8**, answers rise 2/8 → 8/8,
  mean tokens 2014 → 518.

Same flag, same server family, opposite outcomes. `0` means "immediate end", which needs the
chat template to expose a no-think path. Gemma's boot log prints `chat template, thinking = 1`;
Bonsai ships a ChatML-style template with `reasoning_mode: TAG_BASED` (`<think>`/`</think>`) and
no such path, so the request silently no-ops. **A flag being accepted on the command line is not
evidence it did anything** — the same lesson as [[gguf-label-is-not-a-spec]], one layer up.

## Finding 2 — `N>0` works on both, and is enforced precisely

| model | mean reason ch, −1 → 1024 | est. reasoning tokens at bound | budget |
|---|---|---|---|
| Bonsai | 8263 → 4150 | **~1037** | 1024 |
| Gemma | 7806 → 4105 | **~1026** | 1024 |

Two models, two builds, two templates, both landing within **~1.3 %** of the requested budget.
The agreement is the cross-check: chars ÷ 4 is a crude token estimator, and it would not
coincidentally produce ~1024 twice. Answers recover on both (0/8 → 8/8 and 2/8 → 8/8), and
Gemma reaches **8/8 `finish=stop`** — no truncation at all.

## Prediction scoring

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-RB1** | budget 0 LIVE on Gemma | 0.75 | **HELD** — 8/8 → 0/8 reasoning |
| **P-RB2** | budget 0 LIVE on Bonsai | 0.50 | **FALSIFIED** — byte-identical to −1 |
| **P-RB3** | Bonsai tokens drop ≥50 % at budget 0 | 0.70 | **FALSIFIED** — 2048 → 2048, 0.0 % |
| **P-RB4** | positive budget honoured as a bound | 0.65 | **HELD on both**, to ~1.3 % |
| P-RB5 | panel-level effect | 0.80 | **UNSCORED — and its premise is now in doubt, see below** |

Calibration note: after seeing `reasoning_mode: TAG_BASED` in Bonsai's boot log I said P-RB2's
0.50 "looks pessimistic in hindsight." That was wrong in the opposite direction — detecting the
thinking machinery is exactly what makes `N>0` work and says nothing about `0`.

## What this means for the article

**A re-run would change the results, and the flag is not one lever but two.**

- **Bonsai**: only `N>0` helps. It converts cap-deaths into delivered answers, so Bonsai's IFEval
  would **rise** and the ternary win would **widen**. The published headline is understated, not
  threatened.
- **Gemma**: the follow-up the results doc named — *"rerun one Gemma leg with
  `enable_thinking:false`"* — **is reachable**, via `--reasoning-budget 0`. That arm can now be run.

**Experimental-design consequence:** `--reasoning-budget 0` is *not* a matched treatment across
these two arms — it gives Gemma no-think and Bonsai nothing at all. Any re-run that sets `0` on
both and calls it controlled is uncontrolled. **`N>0` is the only setting that acts on both**, and
it is the one a matched re-run should use.

## Limits — one of which undercuts my own P-RB5

- **`max_tokens` 2048, not the panel's 4096.** This matters more than a normal budget caveat:
  the panel found Gemma had **zero** cap hits and failed by *silent closure*, whereas at 2048 she
  cap-dies 6/8. **The halved budget changed Gemma's failure mode**, so this leg cannot speak to
  the silent-closure mechanism at all. P-RB5 assumed a cap would not help Gemma because her
  failure isn't a cap; at *this* budget a cap helps her enormously (2/8 → 8/8). That is not
  evidence against P-RB5 — it is evidence that this instrument doesn't test it. **P-RB5 stays
  genuinely open.**
- **8 prompts, not 541**, chosen as the most-constrained. No IFEval scoring was performed; these
  are delivery counts, not accuracy.
- The 8/8 Bonsai cap-death rate at −1 does **not** restate the panel's 20.3 % empty rate. Different
  budget, different prompt subset. The two numbers must not be presented side by side.
- **Gemma ran MTP off**; a panel re-run would carry MTP. Any MTP × reasoning-budget interaction
  is untested.
- K=1, temp 0, one rig, one build per model.
- Finding 1's mechanism is a hypothesis consistent with the boot logs, not a traced cause — the
  templates' kwargs were not read.
