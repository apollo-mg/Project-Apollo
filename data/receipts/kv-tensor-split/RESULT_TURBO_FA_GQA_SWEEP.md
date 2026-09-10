# The turbo FA kernels are CORRECT at hsk=256 — the collapse is not in flash attention

**2026-09-03.** RX 9070 XT (gfx1201, ROCm), `engines/tq_head` at **`f97400563`**
(turboquant HEAD, post-#295 spill fix), `test-backend-ops test -o FLASH_ATTN_EXT`.
Pre-registered in `PREDICTION_TURBO_FA_GQA_SWEEP.md`. Raw log:
`raw_turbo_fa_gqa_sweep.log` (1,520 lines).

## Headline

**50 turbo-involving flash-attention cases at head size 256, across GQA ratios 1, 2, 4, 6 and
8, batch 1 and 32 — every one passes the NMSE gate. Zero failures. Zero "not supported".**

That includes the exact configurations that destroy generation on this card in
`RESULT_TCQ_2BIT_RDNA4.md`: symmetric `turbo2`/`turbo3`/`turbo4`, and `q8_0`-K with turbo V.

| gqa | K / V | hsk=256, nb=1 | hsk=256, nb=32 |
|---|---|---|---|
| 1, 2, 4, 6, 8 | f16 / f16 | OK | OK |
| 1, 2, 4, 6, 8 | q8_0 / q8_0 | OK | OK |
| 1, 2, 4, 6, 8 | turbo2 / turbo2 | OK | OK |
| 1, 2, 4, 6, 8 | turbo3 / turbo3 | OK | OK |
| 1, 2, 4, 6, 8 | turbo4 / turbo4 | OK | OK |
| 1, 2, 4, 6, 8 | q8_0 / turbo3 | OK | OK |
| 1, 2, 4, 6, 8 | q8_0 / turbo4 | OK | OK |

`2/2 backends passed`.

## Prediction scoring — the main one is FALSIFIED

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | f16 at hsk=256 passes at every nr2 incl. 6 | 0.95 | **HIT** |
| P2 | at least one turbo type FAILS at hsk=256, nr2=6 | 0.75 | **FALSIFIED** |
| P3 | that type passes at nr2=4 (H2 over H3) | 0.40 | **vacuous** — nothing failed |
| P4 | q8_0 K/V at hsk=256 nr2=6 passes | 0.70 | **HIT** |
| P5 | failures span bit depths | 0.65 | **vacuous** |
| P6 | some hsk=256 turbo shapes report "not supported" | 0.35 | **FALSIFIED** — all 50 supported |

I was 0.75 that this would find the bug. It did not. The pre-registration named this outcome:

> "if every turbo case passes NMSE at hsk=256 across all nr2, then the collapse is not
> visible at the kernel-op level and lives higher up (cache write/read path, VBR transcode,
> slot reuse) — which is itself a result and redirects the search."

## What this eliminates

Three hypotheses die here, and one of them was mine from earlier today:

- **H1 (hybrid structure).** Already falsified before the run: Qwen3.5-9B is
  `full_attention_interval = 4` as well, so the clean control and the collapsing model are
  *both* SSM/attention hybrids. Recorded in the Dirk receipt and corrected there.
- **H2 (GQA ratio >= 6).** gqa 6 and 8 pass at hsk=256 with every turbo codec. The GQA ratio
  is not sufficient to produce wrong numbers out of the attention kernel.
- **H3 (head size 256).** hsk=256 turbo passes across the board. Head size is not it either.

**The turbo flash-attention math is fine.** Whatever destroys generation on Qwen3.8-27B is
upstream or downstream of the FA op — candidates in rough order of suspicion: the KV *write*
path (WHT + PolarQuant encode as the cache is filled, vs. the test's freshly-quantized
tensors), VBR transcode between tiers, slot reuse / defrag / checkpoint-restore, or the
auto-asymmetric K-upgrade logic. `RESULT_TCQ_2BIT_RDNA4.md` already recorded that the
trigger is **prompt length on the first request**, which points at the fill path rather than
at steady-state decode.

This also means the whole VGPR-spill line of work in `turboquant#294` — real as it is —
is a *performance* axis and cannot explain the corruption. Worth saying plainly, because
#294 and #311 are adjacent enough to be conflated.

## Coverage facts, source-level (no build required)

| tree | commit | turbo types in the FA sweep | non-F16 KV head sizes | nr2=6 |
|---|---|---|---|---|
| `tq_head` | `f97400563` | TURBO3_0, TURBO4_0 | 64, 72, 128 only | yes, hsk=128 only |
| `llama_cpp_turboquant` | `c26cbdffc` | TURBO3_0, TURBO4_0 | 64, 72, 128 only | **absent entirely** |
| `buun-llama-cpp` | `7a918624b` | **none** | 64, 72 only | no |

- **hsk=256 with any quantized or turbo KV was untested in all three forks until this run.**
  Qwen3.5-9B, Qwen3.6-27B, Qwen3.6-35B-A3B and Qwen3.8-27B are all `key_length = 256`.
- **buun's fork ships VBR** — whose degrade ladder puts a turbo tier at step 1 — with **zero**
  turbo flash-attention coverage at any head size. That is the gap most worth closing for
  buun, independently of this bug.
- Coverage existing is not coverage running: Tom's fleet has no AMD hardware, so no gfx1201
  had executed even the hsk=128 nr2=6 turbo cases before today. They pass.

## Patch used

`tests/test-backend-ops.cpp`, a self-contained block appended after the main FA sweep so the
existing suite is unperturbed: hsk in {128, 256} x nr2 in {1,2,4,6,8} x nb in {1,32} x
{f16, q8_0, turbo2, turbo3, turbo4} symmetric plus {q8_0-K / turbo3-V, q8_0-K / turbo4-V}.
Original file preserved at `scratchpad/tbo.cpp.orig`.

## Next

The model-level repro must be re-run on `f97400563` before anything is reported anywhere —
`RESULT_TCQ_2BIT_RDNA4.md` was measured on buun `02f8581c65` on 2026-08-19, and both forks
have moved since. If it no longer reproduces, that is the finding.
