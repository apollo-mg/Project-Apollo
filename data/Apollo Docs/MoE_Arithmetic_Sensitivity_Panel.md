# MoE Arithmetic-Sensitivity Panel (Router-Flip Hypothesis Test)

**Date:** 2026-07-11. **Rig:** 4× P100 (.194). **Model:** Darwin-36B-Opus-ABLITERATED-HERETIC
i1-Q6_K — arch **qwen35moe** (hybrid-MoE: qwen35 sparse-attention layout + routed experts,
35B total / A3B active). **Corpus/config:** wiki.test.raw, 2k ctx, 32 chunks — matched to the
carve-out panel (`Pascal_FAST_FP16_Carveout_Results.md`). Builds: same patched/unpatched pair
(master `4f37f5197`, branch `sm60-fp32-carveout`). Receipts: `.194:/home/mark/moe_panel/`.
Paired within-model design (every cell vs this model's own patched-f32 truth base), so the
abliterated-finetune identity cancels; abliteration separately exonerated on the hybrid (Jul 10).

## Hypothesis under test

fp16 arithmetic noise flips near-tie router decisions → discrete expert substitution →
fatter catastrophic tail on MoE than the hybrid's arithmetic cell (median 0.005, max 23.7).
**Prediction logged in advance: MoE tail fatter. Outcome: REFUTED** (5th prediction reversal
of the arc, recorded per protocol).

## Results (all vs patched f32-faoff truth base)

| cell | median | 99.0% | 99.9% | max KLD | max Δp | same-top |
|---|---|---|---|---|---|---|
| M0 unpatched f32-faoff (arithmetic-only) | 0.000087 | 0.0081 | 0.038 | 3.85 | 27.2% | 99.19% |
| M1 patched f16-faon (f16 KV cost) | 0.000145 | 0.0085 | 0.042 | 1.23 | 23.2% | 99.05% |
| M2 patched q8-faon (q8 KV cost) | 0.000341 | 0.0138 | 0.071 | 10.88 | 99.2% | 98.75% |

Speed (pp8192 @ d8192 / tg32 @ d8192, 4×P100): patched 304.43 / 42.48 vs unpatched
304.11 / 42.64 — **tie. The carve-out is free on hybrid, dense, and hybrid-MoE.**

## Findings

1. **Router-flip hypothesis refuted for the arithmetic channel.** The hybrid-MoE is ~57× LESS
   sensitive to the fp16-arithmetic mode than the dense-ish hybrid 27B (median 0.000087 vs
   0.004962; flips 0.8% vs 5.0%). Candidate mechanism: error scales with active compute per
   token (A3B touches ~1/10 the matmul volume) — sparsity is noise insulation, not
   amplification. 57× > compute ratio, so layer-type mix contributes; not fully decomposed.
2. **Perpendicular sensitivity map (the headline).** Hybrid 27B: arithmetic-fragile
   (0.005), storage-immune (f16 KV exact-zero, q8 5e-6). Hybrid-MoE: arithmetic-immune
   (0.000087), storage-sensitive (f16 0.000145, q8 0.000341 — **~68× the hybrid's q8 cost**).
   Platform-noise sensitivity is model-CLASS-dependent, and the two axes are independent.
   No published KV-quant quality table accounts for this axis.
3. **Bulk q8 behavior is ordinary rounding** (f16→q8 scales median 2.4×, tail percentiles
   ~1.7× — proportional, not event-driven). **Asterisk:** one token in ~65k under q8 had its
   distribution replaced (max Δp 99.2%), an event class absent under f16. n=1 = anecdote;
   mechanism (router flip vs deep near-tie) unresolved. Cheap follow-up if wanted: more chunks,
   count tokens over KLD 1.
4. **Class labels matter:** these results are for a HYBRID-MoE (sparse attention + sparse FFN =
   maximum insulation). A Mixtral-class dense-attention MoE would separate the attention-density
   and FFN-sparsity contributions — open cell.

## Implications

- **VBR pricing:** ladders calibrated on dense/hybrid models UNDERPRICE KV degradation on MoE
  (~68× class gap at q8). Flag to buun: MoE-specific calibration panels for baked price orders.
- **Fleet:** the patch matters most where Qwopus-class hybrids run; MoE serving was always the
  least-poisoned path. q8 KV on MoE = 1.25% flips — likely fine (Phase-18 task gates passed far
  worse) but no longer "free" as on the hybrid.
- **Paper:** hardware arithmetic sensitivity × model class is a 2-axis interaction nobody has
  mapped; this panel is the first cell block.
