# Result — EXL3 runs on RDNA4: buun's port works, 10× faster on the 9070, and his own tests pass on it

**Run 2026-09-13, 09:40–09:43, on the control plane's RX 9070 XT (gfx1201).** Pre-registered in
`PREREG_EXL3_RDNA4.md` (`83c658f`), driver and scorer `exl3_rdna4.py`, committed with the prereg. Raw
data in `rdna4/`. EXL3 campaign test 8. **This retires ledger entry O1.**

Build: buun `da458765d` ("hip: enable standalone EXL3 execution on wave32 devices"), pushed 21:35 on
2026-09-12, compiled for ROCm at `/mnt/TG_2TB/Projects/buun-da458/build_rocm`. **He has no AMD hardware**;
this is the only RDNA4 in the collaboration.

## Headline

| measurement | test 2, yesterday at `9ae8f0f40` | **today at `da458765d`** |
|---|---|---|
| 0.6B decode | 6.47 t/s | **64.56 t/s — 10.0×** |
| 0.6B, `-ngl 99` vs `-ngl 0` | 4.48 vs 5.24 (**offloading hurt**) | **64.56 vs 7.54 — offloading helps 8.6×** |
| 0.6B VRAM delta | +0.82 GB (KV only) | **+1.45 GB (weights on the card)** |
| 0.6B host RSS | 1.02 GB | **0.72 GB (weights left host memory)** |
| 27B @ 3.00bpw, `mul1`/int8 path | ~0.1 t/s projected | **22.88 t/s**, loaded in 13.4 s, +11.19 GB VRAM |

| id | prediction | result |
|---|---|---|
| P-R1 | the build contains EXL3, with no CUDA-only stub | **CONFIRMED.** `libggml-hip.so`: 0 × "EXL3 is CUDA only" |
| P-R2 | buun's EXL3 tests pass on gfx1201 | **CONFIRMED.** ctest: **100% tests passed out of 11**, rc 0 |
| P-R3 | both models load and answer correctly | **CONFIRMED.** "Paris" from both |
| P-R4 | the `-ngl` A/B inverts | **CONFIRMED.** 64.56 vs 7.54, where test 2 had 4.48 vs 5.24 |
| P-R5 | 0.6B decodes ≥ 3× test 2's median | **CONFIRMED.** 10.0× |
| P-R6 | 0.6B VRAM delta ≥ 1.4 GB | **CONFIRMED.** 1.45 GB |
| P-R7 | the 27B decodes above 6 t/s | **CONFIRMED.** 22.88 t/s |

## What his test suite covers, and why it matters

**All 11 EXL3 tests pass on real RDNA4 silicon**, including the ones that reach the kernels he rewrote:
- **`test-exl3-byte-dot`** — the byte-dot kernel itself, where `__builtin_amdgcn_sudot4` replaces the
  PTX `dp4a`. It **passed**, not skipped.
- **`test-exl3-dense-batch`** across `GGML_EXL3_INT8` = −1, 1 and 2 — so **the int8 path is exercised and
  correct**, not merely the reconstruct fallback.
- **`test-exl3-residual-policy`** across all four modes, and the CPU oracle comparison.

## Two comparisons, both with caveats

- **Against our two P100s:** the 27B at 3.00bpw on one 9070 decodes **22.88 t/s**, about **2×** what
  `.73`'s pair manages at 4.00bpw with tensor split and MTP off (11.26 t/s). **Different bitrate and
  different hardware** — this is not a like-for-like quality comparison.
- **Against GGUF on this card:** a 12.08 GB `AD-IQ3_XXS` measured **32.1 t/s** here on 2026-08-21, so
  EXL3 at 22.88 is roughly **0.71×** a comparable GGUF — the same order as the 0.65–0.85 we measure on
  Pascal. **Different quant recipes, sizes and build**, so treat it as an order-of-magnitude check.

## Why this changes the campaign

**O1 was the campaign's hard scope limit:** EXL3 could not be served from the only always-on box, so
everything else was "EXL3 on the P100 nodes". That is now false — **the 9070 runs EXL3 on the GPU at
usable speed.**

**And this card is where EXL3's advantage should finally be purchasable.** Test 7 found that on `.73`
EXL3 loses on both axes because the node has VRAM to spare. The 9070 does not: with ~13.2 GB usable after
the compositor's 2.7 GB, **the Q6_K daily driver (21.3 GB) does not fit at all, and neither does
UD-Q4_K_M (15.4 GB).** The real choice here is between an IQ3-class GGUF (~12 GB) and EXL3 at 3.00–3.50bpw
(~10–12 GB) — exactly the regime where quality-per-byte decides.

**The next test writes itself:** KLD for EXL3 3.00bpw against an IQ3-class GGUF at 9070-feasible sizes.
It runs on `.73` against the Q8_0 reference already sitting there (`/mnt/HDD/kld/ref.kld`), because the
comparison is about the *files*, not the card.

## For buun

- **A build bug he will hit from any HIP user who builds tests:** configuring with `-DLLAMA_BUILD_TESTS=ON`
  fails with *"HIP_ARCHITECTURES is empty for target test-exl3-byte-dot"*. That target sets `LANGUAGE HIP`
  on a `.cu` source (`tests/CMakeLists.txt:566`) but never receives the architecture list `ggml-hip` takes
  from `GPU_TARGETS`. We worked around it with `-DCMAKE_HIP_ARCHITECTURES=gfx1201`; the fix is one
  `set_target_properties` line.
- **His implementation matches the feasibility note we wrote before seeing it** (`NOTE_EXL3_HIP_PORT.md`),
  idiom for idiom: `sudot4` with the first sign flag false, the funnel shift and bitfield extract as
  plain C, and LOP3 `0x6a` as `(x & mask) ^ bias`.

## Deviations and limits

- **A build-configuration flag was added, no source was patched:** `CMAKE_HIP_ARCHITECTURES=gfx1201`.
- **The scorer misread ctest at first.** Its regex captured "Passed" together with the elapsed-time
  column, so P-R2 initially scored FALSIFIED with every test listed as a failure. The fix takes the
  first word; ground truth (`100% tests passed out of 11`, rc 0) was never ambiguous. **Recorded because
  the first run of a scorer is data about the scorer.**
- **One card, one run per arm, three reps per decode figure.** No quality measurement on RDNA4 — a KLD
  run needs a reference, and the reference lives on `.73`.
- **The 0.6B is format `0.0.1`** and exercises the loader and reconstruct path; the int8 path is covered
  by the 27B arm and by his dense-batch tests.
