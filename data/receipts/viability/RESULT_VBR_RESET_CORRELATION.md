# Result — every degenerate generation follows a `vbr reset`, but most resets are harmless

**Date:** 2026-09-10. **Runs:** `latch-interleaved` A1, A2 (VBR arms), no proxy, 330 W cap.
**Pre-registered:** `PREREG_LATCH_INTERLEAVED.md`. Experiment still running (B2/C2/A3/B3/C3 pending).

> **Update 2026-09-10 — experiment complete; this file's "pending" and "small n" lines are superseded.**
> Final scoring is in `PREREG_LATCH_INTERLEAVED.md`: VBR 3/3 runs affected vs q8_0/f16 0/6 (Fisher
> one-tailed p = 0.0119), and 5/5 degenerate generations followed a `vbr reset`. The localisation
> experiment in the same file then traced it to the fused turbo MMA path:
> `GGML_TURBO_MMA_FUSED=0` and `TURBO_TCQ_HOTSWAP=1` each gave 0/33 bad resets; buun's master
> `d0f82fd41` still gave 5/33.

## Finding

Degenerate generations (pinned at the `-n 4096` cap, the signature previously captured as 4096 `/`)
occur **only** on tasks that experienced a `vbr reset`:

| | A1 | A2 | total |
|---|---|---|---|
| degenerate generations | 1 | 3 | **4** |
| `vbr reset` events | 11 | 5 | **16** |
| degenerate **with** a reset on the same task | 1/1 | 3/3 | **4/4** |
| degenerate **without** a reset | 0 | 0 | **0** |
| resets that were harmless | 10 | 2 | **12** |

**4/4 necessary. 4/16 sufficient (25%).** The path is entered routinely and occasionally goes wrong.

The reset line itself:
```
W slot vbr_reset_on: id  0 | task 443 | vbr reset: cursor 97 and only 0/13128 prompt tokens
reusable (< 0.25) — dropping the prefix; the full re-prefill re-enters at the entry tier
```
So the condition is: low prefix reusability → drop the prefix → **full re-prefill re-entering at
the entry tier**. A tier transition on a live slot.

In A2 the two resets carried an identical `f_sim_best = 0.723` (tasks 114 and 443). One was
harmless; the other produced the first degenerate generation. **Same trigger condition, different
outcome** — which is what a race looks like, not a deterministic input bug.

## Correction to earlier characterisation

`RESULT_SLASH_DEGENERACY.md` and yesterday's notes describe this as latching **permanently until
server restart**. **That is too strong.** A1's task sequence is `.........I.I` — it failed, then
**recovered** on the next task, then failed again. Yesterday's 13-20 task consecutive failure runs
are a more severe presentation, not the only one.

## Arm comparison (this experiment, 330 W cap, no proxy)

| run | KV type | outcome | generations at the `-n` cap |
|---|---|---|---|
| A1 | **VBR** | 2 INFRA, recovered between | 1 of 64 |
| A2 | **VBR** | 3 consecutive INFRA, aborted early | 3 |
| B1 | q8_0 | clean 12/12 | **0 of 66** |
| C1 | f16 | clean 12/12 | **0 of 62** |

## Power is not the mechanism

Sliced per run window from the 20 Hz sampler:

| run | KV | mean of per-second maxima | peak | % seconds > 374 W |
|---|---|---|---|---|
| B1 | q8_0 | 291 W | 382 W | 6.3% |
| C1 | f16 | 321 W | 412 W | **11.9%** |
| A2 | **VBR** | 337 W | 417 W | **2.9%** |

**The arm with the most over-cap excursions (f16, 11.9%) was completely clean; the arm with the
fewest (VBR, 2.9%) failed.** Excursion count does not predict failure. VBR draws the highest
*sustained* power but is the least spiky — consistent with compressed KV trading memory bursts for
continuous dequantisation work.

This does not fully retire the power-cap observation: the 22:55:55 cap change still separates
yesterday's ledger 4/5 vs 0/3, and every run there used VBR, so VBR cannot explain that split.
The compatible reading is that **VBR is necessary for the fault and timing perturbations modulate
its rate** — which would also explain why two unrelated interventions (proxy backpressure, power
cap) each appeared to fix it.

## Status

- **Established:** degenerate generations occur only after a `vbr reset`; 4/4, 0 counterexamples.
- **Established:** q8_0 and f16 arms produced zero capped generations in 128 completed generations.
- **Not established:** the mechanism inside the reset path. Nothing traced in source.
- **Small n:** 2 VBR runs, 16 resets, 4 events. Reps A3/B3/C3 pending.

## For buun (needs Mark's approval and his words)

The actionable statement is not "VBR is broken" but: *the `vbr reset` → prefix-drop →
re-prefill-at-entry-tier path occasionally produces a corrupt slot, ~25% of resets on this
hardware, with an identical trigger condition sometimes harmless and sometimes not.*
