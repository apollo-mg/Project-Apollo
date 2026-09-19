# Result -- Atlas gfx1201 bring-up, S3 (serve): it serves, and 0.85 util is too aggressive on 16 GB

**2026-09-18 (early).** Milestone S3 of Avarok-Cybersecurity/atlas#1126. Model
`maci0/Ornith-1.0-9B-abliterated-NVFP4` (8.89 GB, 12 files), served from the S0 container on the
RX 9070 XT with a desktop session co-resident on the card.

## Atlas serves on a 16 GB consumer gfx1201 board

| check | result |
|---|---|
| server reaches ready | **yes, 6-9 s** (weights page-cached from the download) |
| weights resident | 7.37 GB across 2 shards |
| canary correct | **yes** -- "What is the capital of France?" returns `content: "Paris"`, `finish_reason: stop` |
| output input-dependent | yes; reasoning trace addresses the actual question and its formatting constraint |
| VRAM after shutdown | 2.55 GB, back to the pre-run baseline -- no leak |

That is the PRD's S3 acceptance criteria met: serves within budget, coherent output, canary correct.

## The finding: the stated utilization is marginal on this board

**Three starts, two served, one self-terminated.** The failed run died to Atlas's own guard:

```
OOM watchdog: GPU free memory critically low: 1636 MB (threshold: 2048 MB) [1/3]
                                              1542 MB [2/3]
                                              1605 MB [3/3]
OOM watchdog: 3 consecutive readings below threshold. Terminating to prevent system freeze.
```

`--gpu-memory-utilization 0.85` on 15.9 GB leaves the card hovering around 1.5-1.6 GB free,
under the 2048 MB watchdog threshold, and whether three consecutive samples land below it depends
on what the desktop is doing at that moment. On the 32 GB R9700 the same 0.85 leaves roughly
double the absolute headroom, so this is a 16 GB-specific boundary rather than a general defect.

Worth stating plainly: **n=3 is not a rate.** Two of three surviving establishes that the failure
is real and intermittent, not how often it happens. Characterising it properly is charter (b)'s
job in S4 ("first refusal named; server recovers"), and this is exactly the boundary that charter
exists to find.

The watchdog behaved correctly and its stated purpose -- "to prevent system freeze" -- is the
right call on a card driving a desktop. This is a tuning finding, not a bug.

## CORRECTION (appended after charter (b), 2026-09-18)

**The "32 tokens of margin" reading below is wrong.** I read `4128 max KV tokens` at
`--max-seq-len 4096` as the board's ceiling, 32 tokens above the request. It is not a ceiling.
Charter (b) varied the request and the granted figure tracked it exactly:

| requested | granted |
|---|---|
| 2048 | 2080 |
| 4096 | 4128 |
| 8192 | 8224 |
| 12288 | 12320 |
| 16384 | 16416 |

The `+32` is two blocks of 16-token padding, not headroom. `4128` is simply 4096 rounded up to a
block boundary. The board is nowhere near its limit at 4096 -- it serves 16384 comfortably.

The section below is left as written so the error is visible; everything in it that depends on
4128 being a ceiling should be disregarded. What is still true and unaffected: the itemised
budget, the sysfs source engaging, and the co-tenant exclusion.

## KV cache lands with 32 tokens of margin

```
KV cache: 15.9 GB total x 85% util = 13.5 GB budget; 10.2 GB pre-KV + 0.7 GB reserve
          -> 2.2 GB for KV -> 258 blocks x 16 tok/block = 4128 max KV tokens
KV budget itemised: pre-KV 10.19 GB = weights 7.42 + buffer arena 1.36
          + other 1.41 (CUDA context, driver, co-tenants); reserve 0.68 GB -> KV 2.19 GB
```

The PRD asks for `--max-seq-len 4096`. The board yields **4128** max KV tokens. It fits by 32
tokens, about 0.8%. Any additional co-tenant pressure, or one more GB of anything, and the
requested context does not fit at all. That is the sharpest statement of what 16 GB costs here.

## The sysfs workaround is live and load-bearing

```
free-memory source: amdgpu sysfs /sys/class/drm/card1/device, SCALE build, amdgpu device auto-detected
```

The `cudaMemGetInfo` workaround from atlas#1119 / scale-validation#67 engaged automatically on
this target. Given the measured 4.00x over-charge caps honest capacity reporting at roughly
3.9 GiB on a 16 GB board, a 7.4 GB weight load could not have been sized at all through the
driver API. This is the first direct evidence that the workaround is not a nicety on consumer
RDNA 4 -- without it, serving this model is not possible.

Atlas also correctly excluded the desktop: *"Atlas-own 10.2 GB live in the alloc ledger; 2.9 GB of
co-tenant/page-cache use excluded (set `AVAROK_KV_EXTERNAL_RESERVE_GB` to override)."* The
co-tenant case is handled deliberately rather than by accident.

## Second finding: rocBLASLt has no gfx1201 Tensile library

```
rocblaslt error: Cannot read "TensileLibrary_lazy_gfx1201.dat": No such file or directory
rocblaslt error: Could not load "TensileLibrary_lazy_gfx1201.dat"
WARN spark_runtime::cublaslt: cuBLASLt pre-warm failed (request 1 pays lazy init):
     cuBLASLt AlgoGetHeuristic failed: status 7
```

SCALE bundles hipBLASLt but ships no gfx1201 Tensile library, so the heuristic lookup fails and
pre-warm is skipped -- the first request pays lazy initialisation, and GEMM runs without tuned
kernels for this architecture.

This is a third Spectral-reportable item, distinct from the two already filed, and it is
plausibly relevant to atlas#1116 (prefill GEMM-bound at ~4 TFLOP/s): a GEMM path with no tuned
library for the target is a candidate explanation for part of that shortfall. **Not claimed as
the cause** -- Atlas's W4A16 prefill kernel is custom CUDA through SCALE and would not route
through hipBLASLt. But whatever does route through it is running untuned.

## Third finding: lm_head padded-stride correctness warning

```
WARN lm_head twin uses a PADDED stride (248192 != vocab 248077): this target's w4a16_gemm_t
     MUST accept the `ldb` argument, or decode at padded_n>=5 will read sheared rows.
     Disable with AVAROK_NO_LMHEAD_TGEMM=1.
```

Flagged rather than investigated. It is a correctness condition, not a performance note, and it
names a specific decode regime (`padded_n>=5`) where it would bite. Worth confirming with Tom
whether the r9700 `w4a16_gemm_t` is known to honour `ldb`, since the same warning would appear on
his board and may already be answered.

## Recommendation for the PRD

Lower `--gpu-memory-utilization` for 16 GB parts, or set `AVAROK_KV_EXTERNAL_RESERVE_GB` to
account for a desktop co-tenant explicitly. 0.85 is workable on 32 GB and marginal here. The
value that gives a reliable margin is a measurement S4 should produce rather than a number to
guess at now.

## Next

S4: the six RST acceptance charters. Charter (b), the VRAM boundary, should be run first -- it
is the one this milestone has already started answering.
