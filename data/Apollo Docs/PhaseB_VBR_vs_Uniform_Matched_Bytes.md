# Phase B — VBR Price-Order Mixes vs Uniform Tiers at Matched Bytes

**Date:** 2026-07-11/12. **Rig:** 4× P100 (.194), **patched instrument** (sm60-fp32-carveout on
buun_vbr, commit `a4bc97505`; platform noise floor ~1e-6, anchor receipt `phaseb/anchor_*.log`).
**Config:** wikitext-2, 2k ctx, 32 chunks, all cells vs per-model patched-f32-faoff truth bases.
**Receipts:** `.194:/home/mark/phaseb/*.log` (+ walk generator `walk_schedules.py`).

## Design

Uniform tiers (`-ctk X -ctv X`, TURBO_AUTO_ASYMMETRIC=0 guard) vs **greedy walks of buun's baked
price orders** (`src/llama-vbr-degrade-orders.inc`, q27 + moe) to matched aggregate bpv, applied
via `VBR_LAYER_SCHEDULE` band grammar with `VBR_LAYER_STRICT=1`. Numeric `--vbr-budget` requires
buun's measured policy-ladder artifact (not in repo) — so these mixes are **the states dynamic
VBR's degrade path actually lands on**, not his ladder-optimized schedules (untested, see §5).
Every cell also run under `TURBO_SCORE_LAST_K=64` (l64).

Hybrid mix @4.117: 22×t4, 7×t3, 27K/63V @t8, 11V @t1. Hybrid mix @3.254: 20×t3, 7×t4, 4×t2,
11V @t1. MoE @4.125: walk is exactly uniform t4 (banded order) → reframed as container control.
MoE mix @3.231: 14×t3, 3×t4, 3×t2. Byte parity: −0.19% / +0.15% / ±0 / −0.54% vs uniform.

## Results (median KLD / mean / same-top; l64 median all cells = 0.000000)

**Hybrid (Qwen3.6-27B Q6_K):**

| arm | bpv | median | mean | same-top | l64 same-top |
|---|---|---|---|---|---|
| q8_0 floor | 8.5 | 0.000005 | 0.000957 | 99.795% | — |
| **uniform turbo4** | 4.125 | **0.000774** | **0.0268** | **97.626%** | 97.803% |
| price-order mix | 4.117 | 0.001035 | 0.0431 | 97.174% | 97.168% |
| **uniform turbo3_tcq** | 3.249 | **0.001679** | **0.0359** | **96.768%** | 97.119% |
| price-order mix | 3.254 | 0.001791 | 0.0483 | 96.502% | 96.436% |

**Hybrid-MoE (Darwin-36B qwen35moe A3B):**

| arm | bpv | median | mean | same-top |
|---|---|---|---|---|
| q8_0 floor | 8.5 | 0.000341 | 0.001695 | 98.751% |
| **uniform turbo4** | 4.125 | **0.002469** | **0.006935** | **96.820%** |
| VBR container @ uniform t4 | 4.125 | 0.002469 | 0.006935 | 96.820% (bit-identical) |
| **uniform turbo3_tcq** | 3.249 | **0.004231** | **0.0125** | **95.965%** |
| price-order mix | 3.231 | 0.005206 | 0.01434 | 95.638% |

## Findings

1. **Uniform beats the price-order mix in every comparison.** Margins: hybrid@t4 +34% median,
   hybrid@t3 +7%, MoE@t3 +23% (byte-parity deviations ≤0.6%, cannot account for margins).
   The two t8 holds (27K/63V) did not pay for the t3/t1 sacrifices. On buun's best-measured
   model (q27 order: 160 steps, bench-validated) — the strongest form of the null.
2. **The VBR container is free:** vbr-with-uniform-schedule reproduced native `-ctk turbo4`
   bit-identically (all stats to 6 decimals). Also validates the schedule mechanism itself.
3. **l64 median = 0.000000 universally** (10/10 cells, both classes, all tiers/mixes): the
   typical deep-context token is exact even at 3.2 bpv; ALL cost is early-position + tail.
   Tails also favor uniform (mix l64 means ~2.7× uniform's).
4. **Cross-build reproducibility:** buun-patched fork reproduced stock-patched cells exactly
   (hybrid q8 and MoE q8, 6 decimals) — the patched regime is build-portable.
5. **Scope/caveats:** (a) greedy walks ≠ buun's ladder-optimized schedules — his --vbr-policy
   artifact could compose better; untested until he shares a ladder. (b) his price orders were
   measured on HIS platform/arithmetic — per-layer pricing may not transfer to patched Pascal
   (platform × class × policy interaction — connects to the arithmetic-atlas thesis).
   (c) 2k depth only. (d) Dynamic VBR's core value (degrade vs OOM crash under pressure) is
   NOT tested or challenged here — this is only the static-allocation quality claim.

## Candidate mechanisms for the null

- Greedy marginal pricing doesn't compose: 30+ locally-cheapest steps ≠ jointly-optimal mix.
- Attention renormalizes per-layer: a single very-coarse layer (11V @t1) may distort its
  layer's attention distribution more than the aggregate-bpv accounting assumes, while t8 holds
  add little once t4 is already near-transparent at the median (l64 median 0 at t4 uniform).
- Cross-platform pricing drift (5b above).

## Messages

- **For buun:** container clean, orderings preserved, schedule mechanism verified — but greedy
  price-order landing states lose to uniform at matched bytes on the reference-grade instrument,
  on his home-turf model. Per-class recalibration + testing his ladder artifacts on patched
  Pascal are the natural next steps; we can run any schedule he sends overnight.
- **For Apollo fleet:** at these budgets just run uniform (q8 on hybrids ~free; t4 acceptable;
  on MoE stay ≥q8 where possible — t4 costs 3.2% flips there).
