# Prereg — does EXL3 run on RDNA4 after buun's HIP port? (EXL3 campaign, test 8, ledger O1)

**Written 2026-09-13 ~09:35, before any data from `da458765d`.**

## Why

buun pushed **`da458765d hip: enable standalone EXL3 execution on wave32 devices`** at 21:35 on
2026-09-12, together with fixes for the other three issues we reported (`86eae269c` the e8m0 guard,
`b4545104c` the NaN-blind test, `aadcde38b` an SM86 unroll tune). **He has no AMD hardware**, and Mark's
9070 XT is the only RDNA4 in the collaboration, so this verification is ours to do.

**The baseline is test 2** (`RESULT_EXL3_HIP.md`), measured yesterday on this card at `9ae8f0f40`: EXL3
loaded but every matmul ran on the CPU, `-ngl 99` was **slower** than `-ngl 0` (4.48 vs 5.24 t/s), and the
0.6B decoded at a 6.47 t/s median.

## Setup

- **Hardware:** the control plane's RX 9070 XT (gfx1201).
- **Build:** `da458765d` for ROCm at `/mnt/TG_2TB/Projects/buun-da458/build_rocm`, configured with
  `GPU_TARGETS=gfx1201` **and `CMAKE_HIP_ARCHITECTURES=gfx1201`** (see deviations).
- **Flags:** `-ngl 99 -c 4096 -np 1 -fa on -ctk f16 -ctv f16 --jinja`, port 8195 — test 2's flags.
- **Models:**
  - **H-06** — turboderp `Qwen3-0.6B-exl3` @ 4.0bpw. Format `0.0.1`, **no `mul1` codebook**, so it
    exercises the loader and the reconstruct path, *not* the int8 GEMV. It is test 2's exact file, which
    makes the comparison direct.
  - **H-27-3** — turboderp `Qwen3.8-27B-exl3` @ **3.00bpw**, pinned `6fe61ad6`, ~10.3 GB GPU-resident.
    Chosen because it carries the **`mul1` codebook — the int8 path** — and fits the 9070's practical
    ceiling of about 13 GB after the compositor's 2.7 GB, which 4.00bpw (13.4 GB) does not.
- **Stages:**
  1. **buun's own EXL3 test suite** via `ctest -R exl3` — his correctness tests, never run on RDNA4.
  2. **Per model:** load (readiness is a real completion), one fact question, 3 × 128 greedy tokens.
  3. **The `-ngl` A/B on H-06:** 99 against 0, recording decode, VRAM delta and server RSS — test 2's
     instrument, now preregistered rather than descriptive.

## Predictions

| id | prediction |
|---|---|
| P-R1 | The build contains EXL3: no `EXL3 is CUDA only` string in `libggml-hip.so`, and `exl3.cu.o` among its objects |
| P-R2 | buun's EXL3 tests pass on gfx1201: every `test-exl3-*` returns 0, or the skip code 77; none fails |
| P-R3 | Both models load and answer the fact question correctly |
| P-R4 | **The A/B inverts:** `-ngl 99` now decodes faster than `-ngl 0`, where test 2 measured the reverse |
| P-R5 | H-06 decodes at least **3×** test 2's 6.47 t/s median — the weights now compute on the GPU |
| P-R6 | H-06's VRAM delta at `-ngl 99` is at least 1.4 GB — test 2's +0.82 GB plus the model's ~0.64 GB of weights |
| P-R7 | **H-27-3 decodes faster than 6 t/s** — a 27B at GPU speed on RDNA4, against the CPU path's ~0.1 t/s projection |

## Declared in advance

- **We changed his build configuration to make it configure at all.** Without
  `-DCMAKE_HIP_ARCHITECTURES=gfx1201`, CMake fails: *"HIP_ARCHITECTURES is empty for target
  test-exl3-byte-dot"*. That target sets `LANGUAGE HIP` on a `.cu` source (`tests/CMakeLists.txt:566`)
  but never receives the architecture list `ggml-hip` takes from `GPU_TARGETS`. **This is a finding for
  buun. It is a build-configuration flag on our side, not a source patch** — no EXL3 source is modified
  for this test.
- **The 0.6B does not exercise the int8 path.** H-27-3 does, and it is the arm that decides whether RDNA4
  gets EXL3's fast kernel or only its fallback.
- **Execution is not deployment.** Passing these predictions makes the control plane able to *run* EXL3;
  whether it should *serve* it depends on speed against its GGUF alternatives, which this test only
  begins to answer (P-R7).
- **One card, one run per arm, three reps per decode figure.**
- **Test 2's figures are the comparison** and were taken on the same card, model and flags yesterday.

**Driver:** `exl3_rdna4.py` (`tests`, `models`, `ab`, `score`). Results in `rdna4/`.
