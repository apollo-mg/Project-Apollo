# Pre-registered — does the `head_count_kv` rule survive a controlled fork comparison?

Registered **2026-09-02**, before the matrix ran.

## Why

On 2026-08-28 I derived, from Tom's fork: **`-sm tensor` is correct iff `n_devices <=
head_count_kv`**, because dense attention splits into exactly `head_count_kv` units and fewer
units than devices yields zero-width slices. Flash-Next has `head_count_kv = 2`; 3 and 4 devices
produced garbage. That rule went into receipts, into `FAILURE_MODES.md`, and into a draft to Tom.

On 2026-09-02, **buun's fork tensor-split the same architecture across 4 P100s and produced
coherent text**, with VRAM even to 1.07x (9481 / 9935 / 10175 / 9481 MiB) — verified engagement,
not an inferred fallback. Tom's fork *aborts* on that exact configuration
(`llama-model.cpp:818: only 2 splittable units for 4 devices`).

Three variables differed, so the earlier result cannot be compared directly: **fork**, **quant**
(Q2_K_XL then, IQ4_XS now) and **`-ncmoe`** (none then, 24 now).

## Design — one variable at a time

Model held at **`Qwen3.8-Flash-Next-UD-Q2_K_XL`**, the same quant as the original garbage
observation. Flags identical across all six arms:

```
-c 8192 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 44 -sm tensor
GGML_CUDA_ALLREDUCE=internal          # inert on sm_60, but avoids the NCCL abort (fleet practice)
```

Only **fork** and **device count** vary.

| arm | fork | devices |
|---|---|---|
| B2 / B3 / B4 | buun `7a918624b` | 2 / 3 / 4 |
| T2 / T3 / T4 | Tom `0629f920e` (PR #339, base incl. merged #324) | 2 / 3 / 4 |

**VRAM evenness is the witness that tensor split actually engaged.** A coherent completion alone
proves nothing about which split mode ran — layer split on these flags was 6.36x lopsided,
tensor split 1.07x.

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | T4 aborts at the policy stop | **0.90** |
| P2 | T3 aborts at the policy stop | **0.85** |
| P3 | T2 loads and is coherent | 0.80 |
| P4 | B4 loads, VRAM even, coherent (reproduces today's IQ4_XS result on Q2_K_XL) | **0.65** |
| P5 | B3 loads and is coherent | 0.60 |
| P6 | B2 loads and is coherent | 0.80 |
| P7 | At least one buun arm at 3+ devices is **coherent** — i.e. the rule is fork-specific | **0.65** |

## Reasoning

**P4 at only 0.65** despite having just observed it, because the quant changes here. Granularity is
`lcm(2*n_embd_q, blck_size_perf)` and `blck_size_perf` is quant-dependent, so unit count can differ
between IQ4_XS and Q2_K_XL. That is the single most likely way today's result fails to reproduce.

**P1/P2 high** because Tom's abort is an explicit policy check on unit count, not an emergent
numerical failure — it either fires or it does not, and nothing about the quant should change it.

## Falsifiers

- **B3/B4 garbage or abort on Q2_K_XL** -> today's coherent 4-way was a quant artifact, the
  `head_count_kv` rule stands roughly as written, and I over-corrected.
- **B3/B4 coherent** -> the rule is **fork-specific**, Tom's policy stop is too conservative, and
  every statement of the rule needs the fork named.
- **T2 also aborts** -> Tom's stop is stricter than the rule predicts and the rule is wrong in a
  third way.

## Standing correction

Regardless of outcome, the rule must never again be stated without naming the fork it was measured
on. It was derived on one tree and generalised to an architecture.
