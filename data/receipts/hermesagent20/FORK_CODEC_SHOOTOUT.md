# buun vs TheTom turbo codecs — RDNA4 head-to-head

Control plane, RX 9070 XT (gfx1201, HIP). Model `Qwopus3.5-27B-v3-Q2_K.gguf`, wikitext-2,
ctx 2048 × 8 chunks. Each fork measured against **its own f16 base**. Date 2026-07-28.

## Headline — and why it is NOT "Tom's codec is better"

| codec | buun same-top | Tom same-top | buun med KLD | Tom med KLD |
|---|---|---|---|---|
| turbo4 | 90.200 | **97.642** | 0.021724 | **0.001829** |
| turbo3 | 89.809 | **96.261** | 0.025518 | **0.004304** |
| turbo2 | 87.769 | **95.112** | 0.038516 | **0.005666** |

Tom's implementation is 6.5–7.4 points more faithful at every matched tier. That gap is far
too large to be codec design and is almost certainly an **RDNA4 implementation** difference.

## The evidence that it is a backend problem, not a codec problem

**1. The f16 paths agree almost exactly.**

| fork | f16 PPL |
|---|---|
| buun | 5.8993 |
| Tom | 5.8986 |

0.012 % apart. Both forks compute the same thing at f16, so the model, dataset and harness
are sound on both sides. The divergence is confined to the quantised path.

**2. buun's fork is ~8× slower on this GPU — even at f16.**

| fork | seconds per pass (f16 base) | total |
|---|---|---|
| buun | **28.70** | 237 s |
| Tom | **3.56** | 32 s |

The slowdown is present in the *unquantised* run, so it is not a turbo-kernel cost. It points
to buun's HIP/RDNA4 path falling back to generic or scalar kernels.

**3. buun's fork arms extra machinery unconditionally.** Log preamble on every run, including
the f16 base:

```
VMEAN tap: graph add armed, 16 live layers (pdim 6144)
TCQ1 decode: K/V codebooks (K=baked-in V=baked-in) hotswap=0
TCQ decode: context-adaptive V alpha enabled
```

The V-mean tap and TCQ decode paths are live regardless of the requested KV type. On CUDA
these are the fork's normal operating state; on RDNA4 they are the least-tested code in the
tree.

**4. The same codec scores far better on buun's own target hardware.** The `.73` KLD panel
(2× P100, CUDA sm_60) measured buun's turbo4 at **96.665–96.970 %** same-top across four
depths — 6–7 points better than the 90.200 % measured here. Different model, so not a clean
comparison, but the direction is consistent with an RDNA4-specific regression rather than a
codec that is simply weaker.

## Correct conclusion

**On RDNA4, Tom's turbo implementation is both far more faithful and ~8× faster.** For anyone
serving on RDNA hardware that is decisive and actionable today.

**This says nothing about whose codec design is better.** buun develops and tests on CUDA
(P100/Pascal); Tom's README explicitly claims cross-backend kernel coverage including
"HIP/ROCm RDNA/CDNA". Measuring buun's fork on hardware he does not target is a fair test of
*this fork on this GPU* and an unfair test of *his codec*. A design comparison would require
running both on CUDA.

This is worth reporting to buun as a probable RDNA4 defect, not as a codec loss.

## Limits

- One model (Q2_K weights — already heavily quantised, which may amplify KV sensitivity), one
  dataset, ctx 2048, 8 chunks, n=1 per cell.
- Codec overlap only: buun additionally ships turbo8 and turbo{1,2,3}_tcq, Tom ships none of
  those, so buun's full range is not represented.
- No CUDA arm. Without one, "implementation vs design" cannot be fully separated — it is
  inferred from the f16 agreement, the 8× f16 slowdown, and the `.73` CUDA numbers.
- Bases were generated per fork by design; this prevents fork-level f16 differences from
  contaminating the codec measurement, and the near-identical PPL confirms it was safe.

## Provenance

`~/projects/HermesAgent-20/fork_codec_shootout.sh`, results in
`~/projects/HermesAgent-20/fork_shootout/`, bases in `/mnt/TG_2TB/kv_shootout_bases/`
