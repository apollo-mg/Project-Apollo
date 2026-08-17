# RDNA4 is clean where Pascal collapses — the WMMA gate predicts it

**2026-08-17**, control plane **RX 9070 XT (gfx1201, RDNA4, ROCm/HIP)**.
Binary **TheTom/llama-cpp-turboquant `f050a2501`** ("fattn-vec: gate the turbo K split on
the LUT, not on D" — the PR #295 fix commit), `version: 10465`, HIP build.
`.73` ran **`f6124e9`**, the #295 *merge* commit, on CUDA sm_60. **Same fork, same PR**, so
this is an architecture comparison, not a fork comparison.

Model `Qwen3.5-9B-Q8_0`, **D=256**, 16 heads / 4 KV (**GQA 4:1**, below Tom's 6:1 gate, so
`TURBO_AUTO_ASYMMETRIC` cannot fire; pinned to 0 anyway). `-ngl 99 -c 16384`, single GPU.
Raw `~/xfork_rdna4/`, log in scratchpad, script `kv_rdna4.sh`.

## Every arm clean, 3/3

| arm | K | V | sm_60 (D=256) | **RDNA4** |
|---|---|---|---|---|
| R0 | f16 | f16 | clean | **clean 3/3** |
| R1 | `q8_0` | `q8_0` | **COLLAPSE** | **clean 3/3** |
| R2 | `q4_0` | `q4_0` | **COLLAPSE** | **clean 3/3** |
| R3 | `q8_0` | f16 | clean | **clean 3/3** |
| R4 | f16 | `q8_0` | clean | **clean 3/3** |
| R5 | `q8_0` | `q4_0` | abort¹ | **clean 3/3** |
| R6 | turbo3 | turbo3 | abort¹ | **clean 3/3** |
| R7 | `iq4_nl` | `iq4_nl` | abort¹ | **clean 3/3** |

¹ **on sm_60 those three abort only under `-sm tensor`.** See the scope limit below — R5/R6/R7
passing here is not evidence about the abort.

## The result: an architecture-level dissociation matching the source gate

R1/R2 are the load-bearing arms. `q8_0` and `q4_0` symmetric at D=256 collapse
deterministically on sm_60 — 512 `/`, first request, both forks, both split modes — and are
**clean on RDNA4 with the same fork at the same PR**.

The standing mechanism is that `fattn.cu`'s D=256 fused path is gated on
`turing_mma_available() || amd_wmma_available()`:

| | Turing MMA | AMD WMMA | gate | `q8_0` K+V @ D=256 |
|---|---|---|---|---|
| Tesla P100 (sm_60) | no | no | **false** | **collapse** |
| RX 9070 XT (gfx1201) | no | **yes** | **true** | **clean** |

Two architectures sitting on opposite sides of a runtime capability check behave exactly as
the check predicts. That moves the mechanism from "the source suggests" to a tested
dissociation.

**This is a different and stronger warrant than the one that failed earlier.** `AFM-17` was
logged this morning after three predictions built on *compile-time dispatch-table entries*
were all wrong — a table entry existing said nothing about which path ran. This gate is a
**runtime capability check**, the thing that actually selects the path. Predicted R1 clean at
0.65 for exactly that reason; it came back clean.

## Scope of the bug, now complete

**D=256 model + K *and* V both quantized + hardware with neither Turing MMA nor AMD WMMA.**

That is Pascal and older NVIDIA, and pre-RDNA3 AMD, running the Qwen3.5/3.6/3.8 families.
Silent, deterministic, on the first request, on both forks, under both split modes. It is
also why the bug is not widely known: modern hardware takes the fused path and never sees it.

## Scope limit — this ladder cannot test the abort

The 9070 XT is a **single GPU**, so there is no tensor split and no split-axis resolution.
`RESULT_XFORK2.md` established the abort **requires `-sm tensor`** (turbo3 symmetric aborts
under tensor split, runs clean under layer split on the same binary).

So R5/R6/R7 coming back clean says **nothing** about whether RDNA4 would abort with two GPUs.
It reflects the absence of the split path, not its correctness. Testing the abort on RDNA4
needs a second AMD card, which this fleet does not have.

What R6 *does* establish, incidentally: **turbo3 symmetric runs clean on RDNA4 at GQA 4:1**
with the auto-asymmetric guard off — a genuine turbo3 measurement, unavailable on sm_60 under
tensor split where the same configuration aborts.

## Detector note — the old threshold would have inverted this result

R1 `req2` came back `maxrun=42`. The **original** detector threshold flagged `maxrun > 40` as
degenerate; `AFM-15` raised it to `> 200` after a markdown table rule triggered a false
positive that nearly implicated context length.

Under the old threshold R1 would have been reported **DEGENERATE**, and the headline of this
receipt would have been the exact opposite of the truth. The threshold correction paid for
itself here.

## What this does NOT establish

- **Not a fidelity claim.** "Clean" is not-degenerate, not verified quality. RDNA4 `q8_0` KV
  being clean says nothing about how good it is.
- **One AMD generation.** gfx1201 only. RDNA2/older AMD lack WMMA and would, under this
  mechanism, be predicted to collapse — untested, and there is no such card here.
- **Not the abort**, per the scope limit above.
- **`RESULT_GFX1201.md` still stands**: RDNA4 has its own D=256 VGPR-spill problems in these
  same kernels. Clean output and efficient kernels are different questions.
