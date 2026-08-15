# PREREG — does MTP compose with tensor split? {single, layer, tensor} x {MTP off, on}

**Sealed 2026-08-15, before any cell ran.** Node `.73`, 2x Tesla P100 (sm_60), 150 W /
1063 MHz under load, `buun_vbr`, `Qwen3.8-27B-UD-IQ3_XXS` (unsloth, 11.09 GiB),
`-ngl 999 -c 8192 -fa on -np 1`, temp 0 / top_k 1 / seed 1234, `--spec-draft-n-max 3`.
12 arms, palindrome order, `REPS=2` (10 samples per arm).

## The question

`RESULT_P100_SM_TENSOR.md` established that `-sm tensor` is 1.623x over one card while
`-sm layer` is inert (0.995x). Separately, MTP measured 1.52x on this node under layer split.
Whether those compose is not derivable from either result.

The mechanism argues both ways, which is the reason to run it:

- The MTP **draft** step is a single small layer (`blk.64`, 8 tensors). Under tensor split
  its ops are split across both cards with an all-reduce each — a poor compute-to-
  communication ratio at that size, over PHB with no NVLink. Predicts MTP pays **less**
  under tensor split.
- The MTP **verify** step evaluates 3-4 tokens per forward pass instead of 1, i.e. more
  compute per all-reduce than ordinary decode. Predicts MTP pays **more** under tensor split.

## Why the single-GPU row is included

This model fits on one P100, so the no-split row gives the MTP multiplier with no
interconnect involved at all. It is the reference the other two rows are read against —
without it, a tensor-split multiplier has nothing to be "less than". This is the same
mistake the split-mode A/B nearly shipped with, caught only when the single-GPU arm was
added late.

Existing numbers this ladder should reproduce (different harness, same node): single off
**8.585**, layer off **8.540**, tensor off **13.930**, layer on **13.00**.

## Acceptance rate is a control here, not just a metric

Draft acceptance is a property of the draft/target pair, not of where the tensors live, so
it should be near-constant across split modes. If it moves substantially, the split is
perturbing numerics enough to change draft/target agreement — which `qwen38-splitmode`
Finding 4 already shows happens to greedy output at temp 0. That would be a result in its own
right, and it would mean throughput comparisons across split modes are not comparing the same
computation.

## Predictions, sealed

| # | prediction | conf |
|---|---|---|
| P1 | The layer-split MTP multiplier is within 5 % of the single-GPU MTP multiplier | 0.75 |
| P2 | All three split modes show MTP net-positive (> 1.0x) | 0.85 |
| P3 | Aggregate draft acceptance varies < 3 pp across the three split modes | 0.70 |
| P4 | `tensor + MTP on` is the fastest absolute cell | 0.75 |
| P5 | Composition is **sub-multiplicative**: tensor+MTP < (1.623 x MTP multiplier) x single-off | 0.70 |
| P6 | The tensor-split MTP multiplier is **lower** than the layer-split one | 0.55 |

P1 follows from layer split being inert on a single sequence: if it changes nothing for
ordinary decode it should change nothing for speculative decode either. P6 is the coin-flip —
it is the draft-step-overhead argument against the verify-batch argument, and 0.55 is honest
about not knowing.

## What would falsify the framing

If P3 fails — acceptance moves >3 pp with split mode — then split mode is changing draft
agreement, the cells are not measuring the same computation, and the throughput comparison
needs restating before any composition claim is made.

## Known limits before starting

- One model, one quant, one context, 2 cards, `-np 1`. Batching is untested and is the
  regime where layer split should stop being inert.
- `--spec-draft-n-max 3` only. The draft depth interacts with the compute-per-all-reduce
  argument directly, so a single depth cannot separate the two mechanisms above — it can only
  show the net.
- Throughput and acceptance only. No quality measurement.
- The unsloth `UD-IQ3_XXS` MTP head is `IQ4_XS` x5 + `IQ3_S` x3, quantised without imatrix
  coverage (`qwen38-packagers`). Whatever acceptance this ladder measures is that head's, not
  a well-calibrated head's.
