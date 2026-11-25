# RESULT: ROCm 10.1 on the desktop works for llama.cpp once CachyOS's broken HIP runtime is swapped for Arch's build -- same speed, small numeric drift, totals unchanged; no op failure is caused by 10.1; buun's newest commit cannot build for AMD at all, on any ROCm

**Prereg:** `PREREG_ROCM10.md` (`ac79eb99`) with Deviation 1 (B4 via `llama-perplexity`), Deviation 2 (the turboquant gate
and buun's CMake flag) and Deviation 3 (the measures rerun on Arch's HIP runtime). **Runs:** 2026-11-24, RX 9070 XT, kernel
7.3.5-2-cachyos, system ROCm 10.1 (CachyOS packages). **Records:** `raw/state_builds.log`, `raw/state_measures.log` (first
pass, CachyOS runtime), `raw/state_measures_arch.log` (Arch runtime), build and op-test logs in `raw/`; the runtime bug in
`NOTE_CACHYOS_HIP_BUG.md`.

## The runtime

CachyOS's `hip-runtime-amd 10.1-2.1` segfaults creating a second HIP stream (a 10-line test: 17 of 20 runs; Arch's 10.1-2
build of the same version: 0 of 20). The first measure pass ran on it, so its failures -- servers dying on load, op tests
crashing (exit 139) -- are that runtime's, not the builds'. Reported as CachyOS/CachyOS-PKGBUILDS#2196. Everything below runs
on the system's ROCm 10.1 with only Arch's `libamdhip64` swapped in (`tools/rocm101arch.sh`).

## Results

| | result |
|---|---|
| **B1** builds and runs (0.7) | **4 of 5 build and answer correctly** (buun 38ada0e1b, PR 32588 4bc61eed7, mainline 33aeb17f8, turboquant f7c3638e8); buun's head 1e50db7be does not build (below). Fails as registered (5 of 5 predicted) |
| **B2** op tests, mainline clean in MUL_MAT / MUL_MAT_ID / FLASH_ATTN_EXT (0.7) | **fails narrowly:** mainline 21,002 of 21,003 pass; the one failure is MUL_MAT f16 x f32 at m=16, n=2,105,344, k=32 (error 0.0042 against 0.0005). It fails the same way on the 7.2.4 runtime (0.0043), so 10.1's runtime is not the cause. Turboquant: 21,203 of 21,204; its one failure (MUL_MAT on its own `q8_cr` type, random data) is flaky on both runtimes: 2 failing tests in 5 runs on 10.1, 4 in 5 on 7.2.4 |
| **B3** same source, 7.2.4 build vs 10.1 build: not byte-identical (0.6) | **holds:** Granite 3B (buun 38ada0e1b) 220 of 240 answers identical, Qwen3.5-9B (4bc61eed7) 168 of 240 |
| **B3** at most 10 grades change (0.7) | **holds for Granite (4), misses for Qwen (11).** Totals: Granite invented / hard / easy 81 / 12 / 25 both; Qwen 65 / 42 / 36 -> 65 / 41 / 34 |
| **B4** speed (reported) | prompt processing the same (0.57-0.64 s per pass on 7.2.4, 0.63 on 10.1); decode about 2 % faster on 10.1 (Granite 100.7 -> 102.4 tok/s, Qwen 57.0 -> 58.4, the M1 medians); perplexity 8.4718 -> 8.4759 (20 chunks) |

## buun's head (`1e50db7be`), two build bugs for buun

1. With tests on, CMake stops: `HIP_ARCHITECTURES is empty for target "test-exl3-byte-dot"` (a HIP test target that
   never gets the architecture list). Workaround: `-DCMAKE_HIP_ARCHITECTURES=gfx1201`.
2. With that, the HIP build stops in `ggml/src/ggml-cuda/dsv4-hc.cu` (lines 275, 389): `no matching function for call to
   '__ldcg'` on an `unsigned int *`. HIP defines `__ldcg` only for `__half` and `__half2`, in 7.2.4 as in 10.1, so this
   file cannot build for AMD on any ROCm: not a 10.1 regression. A volatile or atomic load would be the portable form.

## Reading

ROCm 10.1 itself is usable on the 9070 for llama.cpp: with a working HIP runtime, every build that compiles runs, speed is
unchanged (decode a little faster), and the same source recompiled under LLVM 24 changes wording on a share of answers
while the scored totals hold. The crash was an upstream clr alignment bug (ROCm/rocm-systems#11256, open since 2026-09-04) that CachyOS's CPU-optimised build of one library exposes and Arch's generic build does not (`NOTE_CACHYOS_HIP_BUG.md`). No op failure was introduced by 10.1;
the forks' issues are buun's HIP portability (any ROCm) and a flaky turboquant test tolerance.

## Limits

One card, one OS image; the mainline MUL_MAT failure was not run on a 7.2.4-compiled binary of the same commit (tests were
not built in the older builds), so compiler versus long-standing cannot be told apart; op tests compare against the CPU
backend, not whole models.
