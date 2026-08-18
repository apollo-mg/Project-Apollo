# Turbo KV overhead is a fixed 128 KiB, not a per-token cost — finding 4 is retracted

**2026-08-18**, `.194`, quad Tesla P100 (sm_60). buun `02f8581`, `Qwen3.8-27B-Q6_K`, D=256.
Load-only: contexts are allocated, the `KV buffer size` lines are read, nothing is inferred.
Raw `u5e.log`, script `u5e_kvsize.sh`, per-config logs `~/u5e_raw/` on `.194`.

Resolves the ambiguity left open in `RESULT_U5CD_PLACEMENT.md` **finding 4**, which reported
that every turbo type allocated ~+0.5 bpv more than its block layout implies and concluded
that U5c's matched-budget premise — and therefore its 8-bit verdict — was unsound.

**That conclusion was wrong. Finding 4 is retracted.**

## Measured allocation, quantized context only, summed across all 4 devices

| codec | Δ vs layout @512 | @4096 | @16384 | measured bpv @16k | block layout |
|---|---:|---:|---:|---:|---:|
| f16 | 0.00 | 0.00 | 0.00 | 16.000 | 16.0 |
| `q8_0` | 0.00 | 0.00 | 0.00 | 8.500 | 8.5 |
| `q4_0` | 0.00 | 0.00 | 0.00 | 4.500 | 4.5 |
| turbo8 | **0.12** | **0.12** | **0.12** | 8.127 | 8.125 |
| turbo4 | **0.12** | **0.12** | **0.12** | 4.127 | 4.125 |
| turbo3 | **0.13** | **0.12** | **0.12** | 3.502 | 3.5 |
| turbo2 | **0.13** | **0.12** | **0.12** | 2.502 | 2.5 |

(MiB. 0.13 vs 0.12 is display rounding on a 2-decimal field; the underlying constant is
0.125 MiB = **128 KiB**.)

**Stock types allocate exactly their block layout at every context size. Every turbo type
carries a constant 128 KiB on top, independent of `n_ctx` across a 32× span.** It is a fixed
buffer — a codebook or scratch allocation — not a per-token cost. Measured bits/value
converges on the layout value as context grows (turbo8: 8.185 → 8.133 → **8.127** against a
layout of 8.125).

## Why finding 4 got it backwards

U5c ran at **136 tokens**, where the whole KV cache is 1–4 MiB. A fixed 128 KiB is **3–10 %**
of that, which was enough to invert the apparent ordering and make turbo8 look *more*
expensive than `q8_0` despite encoding at 8.125 bpv against 8.5. At 16k the same 128 KiB is
0.02 %.

**Consequences, in both directions:**

- **The block arithmetic is correct for any realistic deployment.** The bits/value figures
  used throughout this campaign — `q8_0` 8.5, turbo8 8.125, `q4_0` 4.5, turbo4 4.125,
  turbo3 3.5, turbo2 2.5 — are right, and `RESULT_U5B_BUUN.md`'s cost claims stand.
- **U5c's matched-budget premise is restored**, and with it the 8-bit tier's arithmetic. The
  "unsound" marking placed on that verdict by finding 4 is lifted.
- **But the 8-bit tier still does not support the symmetry hypothesis**, for the separate and
  unaffected reason given in the first amendment: only arm C dips below the interpolation
  while arm B sits on it. One mixed arm dipping is a placement effect; symmetry would move
  both. That argument never depended on the budget question.
- **The swap tier's symmetry verdict remains withdrawn** on the kernel-path confound
  (`fattn.cu:2638`), which this measurement does not touch.

## The correction chain, recorded deliberately

This is the third link in one day: U5c produced a result → finding 4 challenged its premise →
U5e overturned finding 4. **A correction is not automatically more reliable than the thing it
corrects**, and finding 4 was published with a caveat ("fixed padding would vanish at 32k")
that turned out to be the true explanation. The caveat was right and the headline was wrong.

`AFM-18` (new): *when a measurement disagrees with source arithmetic, test whether the
disagreement scales before concluding the arithmetic is wrong.* One extra context size would
have settled it immediately; the original observation had only one.

## What this is worth to buun

**Every turbo KV type carries a fixed 128 KiB per context that the stock types do not.**
Invisible at long context and irrelevant to the fidelity comparisons — but on a small-context
or many-slot server it is real, and it is not in any block-layout table. Whether that is a
codebook that could be shared across contexts is a question for him, not a claim from here.
