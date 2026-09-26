# On buun's current build, MTP now doubles EXL3 on RDNA4: the GGUF speed lead at matched size falls from 2.1-2.4x to 1.2-1.3x

**2026-09-26, 11:55-12:06**, RX 9070 XT (gfx1201), buun **`0b2789f23`** (built for gfx1201 with the `da458765d`
build's options). Prereg `PREREG_EXL3_RDNA4_RERUN.md` (`96e2294`). The instrument is unchanged from
`RESULT_EXL3_RDNA4_MTP.md` (09-13, `da458765d`): the same script `exl3_rdna4_mtp.py`, the same four arms, depths
0-3, `llama-bench -ub 1..16`. Only the build differs. Raw: `rdna4_mtp_0b278/`.

## Before and after

| arm | build | d0 | d1 | d2 | d3 | best | MTP gain |
|---|---|---:|---:|---:|---:|---:|---:|
| **EXL3 3.00 bpw** (~10.3 GB) | 09-13 | 22.49 | 22.22 | 20.78 | 20.04 | 22.49 | 1.00x |
| | **today** | 22.60 | 22.22 | **44.40** | 43.50 | **44.40** | **1.96x** |
| GGUF GSQ-RCO IQ3_XXS (10.02 GB) | 09-13 | 30.54 | 43.55 | 54.02 | 53.94 | 54.02 | 1.77x |
| | today | 30.44 | 43.51 | 57.40 | 51.08 | 57.40 | 1.89x |
| **EXL3 3.50 bpw** (~11.8 GB) | 09-13 | 22.83 | 22.31 | 21.02 | 20.74 | 22.83 | 1.00x |
| | **today** | 22.68 | 22.21 | **40.89** | 40.91 | **40.91** | **1.80x** |
| GGUF i1-IQ3_M (12.21 GB) | 09-13 | 28.21 | 41.58 | 47.70 | 47.48 | 47.70 | 1.69x |
| | today | 28.74 | 41.48 | 48.61 | 48.27 | 48.61 | 1.69x |

**GGUF's lead at its best depth:** ~10 GB **2.40x -> 1.29x**; ~12 GB **2.09x -> 1.19x**.

The MTP gate holds in every arm: drafts engage, and drafted-per-token rises with depth.

## Why: the EXL3 4- and 8-row path was rewritten

`llama-bench -p 64`, throughput at micro-batch *m* relative to *m* = 1 (A(m)):

| | A(2) | A(4) | A(8) | A(16) |
|---|---:|---:|---:|---:|
| EXL3 3.00 bpw, 09-13 | 1.16 | 1.27 | 1.25 | 1.59 |
| **EXL3 3.00 bpw, today** | 1.16 | **3.59** | **4.26** | 1.57 |
| GGUF IQ3_XXS, today | 1.72 | 2.32 | 3.37 | 6.46 |

- **3-8-row batches now amortize.** A(4) went from 1.27 to 3.59, now *above* GGUF's 2.32. A depth-2 or depth-3 MTP
  verify is exactly a 3-4-row batch, so speculative decoding pays for itself.
- **2 rows did not change** (1.16), which is why depth 1 is still flat.
- **16 rows did not change** (1.57). Past 8 rows EXL3 takes its reconstruct + BLAS path (`exl3-on-pascal`), which
  this work did not touch.
- **Source:** buun's EXL3 int8 GEMV rework between the builds: `exl3-gemv-int8.cuh` (+414 lines), a new
  `exl3-int8-warpk.cuh`, and `exl3.cu` (+367), 09-17/18. The commits are titled for NVIDIA SM86/SM75; the 9070
  inherits the shared code through HIP.

## Numerics: the faster path computes the same thing (a post-run validity check, not registered)

EXL3 3.00 bpw, WikiText-2 test (sha256 `173c87a5...`), 10 x 512 tokens, **`-ub 4`**, which forces the rewritten
4-row path. The old build saved logits (`--kl-divergence-base`), and the new build was scored against them:

| | value |
|---|---|
| mean KLD, new vs old | **0.000305 +/- 0.000013** (max 0.0098) |
| same top-1 | **99.22 %** |
| PPL(new) / PPL(old) | 1.0021 +/- 0.0010 |
| seconds per 512-token pass at `-ub 4` | 17.49 (old) -> **6.73 (new)** |

The drift is about 2x the noise between two HIP decoders measured last night (0.00015,
`bonsai-hip/RESULT_BONSAI_HIP_VALIDATION.md`). That is consistent with a reordered accumulation, and small next to
EXL3's own quantization error. It is not zero; buun may want to know it exists.

## Predictions

| # | claim | result | verdict |
|---|---|---|---|
| R1 | EXL3 best within +/-5 % of 22.49 / 22.83 | 44.40 / 40.91 | **false** (+97 % / +79 %) |
| R2 | GGUF best within +/-5 % of 54.02 / 47.70 | 57.40 (+6.3 %) / 48.61 (+1.9 %) | **false** (one of two; one run per point) |
| R3 | EXL3 MTP gain <= 1.05 | 1.96 / 1.80 | **false** |
| R4 | E3 A(4) within +/-10 % of 1.27 | 3.59 | **false** |
| R5 | the gap stays in [1.9, 2.6] | 1.29 / 1.19 | **false** |

I predicted no change, at 0.55-0.70, reading the commit titles as "not an EXL3 kernel change". The titles were
SM86/SM75, but the shared code path reached RDNA4. **Lesson: on buun's tree, a commit titled for one architecture
can move another.**

## What it means

- **The 09-13 decision table ("GGUF is faster at every quality level, EXL3 smaller at every quality level") needs
  its speed half reweighed on this build.** GGUF is still faster at matched size, but by 1.2-1.3x, not 2.1-2.4x.
- **EXL3's quality edge is 24 % lower KLD than GGUF at matched VRAM** (`RESULT_EXL3_KLD.md`, measured on Pascal).
  On the 9070 that edge now costs about a quarter of the speed instead of more than half. On a 16 GB card where
  every GB matters, EXL3 3.50 bpw at 40.9 t/s is now a serious option.
- **What is left for buun:** the 2-row case (depth 1) and the > 8-row path (A(16) 1.57, against GGUF's 6.46).
  Prefill is still where GGUF wins by far.

## Not established

- One run per point, as on 09-13.
- Decode speed on one prompt; the quality numbers are from the Pascal KLD receipt, not remeasured on the 9070.
- The numerics check covers one bpw at `-ub 4`.
