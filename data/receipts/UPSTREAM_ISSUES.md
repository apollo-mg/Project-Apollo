# Upstream issues register

Bugs and quirks we found in other people's software, kept in one place so they can be handed on when useful. Each entry:
what, where (project and commit), how it shows, how to reproduce, the workaround, where it stands, and the receipt. Newest
first. "Reported" means someone filed it; "not reported" means the facts are here if anyone needs them.

---

## 2026-07-11 (status 2026-11-27) -- llama.cpp: Tesla P100 (sm_60) silently does fp32 math in fp16

- **Where:** ggml-org/llama.cpp mainline, `ggml/src/ggml-cuda/common.cuh` (the `FAST_FP16_AVAILABLE` device macro and the
  host `fast_fp16_available()` / `fast_fp16_hardware_available()` gates exempt sm_61 only). Still present in `33aeb17f8`.
- **Shows:** on P100s, flash-attention tile kernels and cuBLAS run in half precision: median KLD ~0.002 against an f32
  reference, ~3.5 % greedy top tokens flipped; P100s sit ten times farther from the CPU than the desktop 9070 (mean KLD
  0.0065 vs 0.00067, `stack-drift/RESULT_STACK_DRIFT.md`, which left the cause untested).
- **Fix:** three lines carving sm_60 out like sm_61 (`tools/patches/sm60-fp32-carveout.patch`): median KLD 0.000001,
  same-top 99.9 %.
- **Status:** reported by Mark as #25593; **closed 2026-11-27 as not planned by the stale bot**, still labelled
  "bug-unconfirmed". Merged in buun-llama-cpp (#80) and llama-cpp-turboquant (#212); mainline and mainline-based forks
  lack it.
- **Receipt:** `data/Apollo Docs/Pascal_FAST_FP16_Carveout_Results.md`.

## 2026-11-25 -- llama.cpp: looped models split across GPUs by loop slots, not stored layers

- **Where:** ggml-org/llama.cpp mainline `33aeb17f8` (2026-11-24), architecture `inkling2_loop` (Inkling-2-Mini).
- **Shows:** on two GPUs, `-sm layer` puts every physical layer on the first card. With AtomicChat's AD-Q6_K (23.8 GB) the
  first P100 is asked for 22.8 GB and the load fails (`cudaMalloc failed: out of memory`). `-ts 1,1` changes nothing.
- **Why:** `load_arch_hparams` sets `n_layer_all` to the cache-slot count (24 physical + 2 x 12 loop passes = 48), and the
  device split in `llama-model.cpp` (`get_layer_buft_list`) runs over `n_layer_all`. Only slots 0-23 hold weights, so an
  even split maps all of them to device 0.
- **Repro:** two 16 GB cards, `llama-server -m Inkling-2-Mini-AD-Q6_K.gguf -ngl 99 -sm layer -fit off` (with or without
  `-ts 1,1`).
- **Workaround:** `-ts 1,3` on two cards (physical 0-12 on GPU 0, 13-23 and the output on GPU 1).
- **Status:** not reported. Single-GPU setups never see it. An open PR on looped-MoE placement (#32777) is related.
- **Receipt:** `inkling-mini/raw/diag_split.log`, `inkling-mini/PREREG_INKLING_MINI.md`.

## 2026-11-24 -- ROCm 10.1 HIP runtime (CachyOS build) segfaults creating a second HIP stream

- **Where:** CachyOS `hip-runtime-amd 10.1-2.1` (cachyos-extra-v3, x86_64_v3); root cause upstream in AMD's clr.
- **Shows:** any program that creates a second HIP stream usually crashes (17 of 20 runs); every llama.cpp build crashes at
  context creation (`hipStreamCreateWithFlags`); kernel log: general protection fault at `libamdhip64.so.7.16.0` +0x74d5b8.
- **Why (traced by others):** `amd::ReferenceCountedObject` has a class-scope `operator new(size_t)` without an
  `align_val_t` overload, so `roc::VirtualGPU` (64-byte-aligned members) gets 16-byte heap storage; CPU-optimised builds
  emit aligned 32/64-byte stores that fault when the address happens to be misaligned. Arch's generic build does not.
- **Repro:** `stack-drift/hip_stream_repro.cpp` (10 lines), `hipcc --offload-arch=gfx1201`, run 20 times.
- **Workaround:** Arch's `hip-runtime-amd 10.1-2` library via `tools/rocm101arch.sh`; old builds via `tools/rocm724.sh`.
- **Status:** reported -- ROCm/rocm-systems#11256 (2026-09-04, open) and #14003; CachyOS #2137 (open), #2143 and ours
  #2196 (closed as duplicates).
- **Receipt:** `stack-drift/NOTE_CACHYOS_HIP_BUG.md`.

## 2026-11-24 -- buun-llama-cpp: the head does not build for HIP on any ROCm

- **Where:** spiritbuun/buun-llama-cpp `1e50db7be` (master, 2026-11-24).
- **Shows (1):** with `LLAMA_BUILD_TESTS=ON`, CMake stops: `HIP_ARCHITECTURES is empty for target "test-exl3-byte-dot"`.
  Workaround: `-DCMAKE_HIP_ARCHITECTURES=gfx1201`.
- **Shows (2):** then `ggml/src/ggml-cuda/dsv4-hc.cu` lines 275 and 389: `no matching function for call to '__ldcg'` on an
  `unsigned int *`. HIP defines `__ldcg` only for `__half` and `__half2` (ROCm 7.2.4 and 10.1 alike), so the file cannot
  build for AMD at all. A volatile or atomic load would be the portable form.
- **Status:** facts passed to buun informally (Mark, 11-24); not filed.
- **Receipt:** `stack-drift/RESULT_ROCM10.md`, `stack-drift/raw/build_buun_1e50db7b_dev2.log`, `raw/b2_followup.txt`.

## 2026-11-24 -- llama-cpp-turboquant: `q8_cr` MUL_MAT fails on some random inputs on gfx1201

- **Where:** TheTom/llama-cpp-turboquant `f7c3638e8` (feature/turboquant-kv-cache); also `cc1a79194` (2026-09-03).
- **Shows:** `test-backend-ops -b ROCm0 -o MUL_MAT -p q8_cr` fails some of its 68 cases on random data (the test seeds from
  `std::random_device`), errors 0.00057 to 0.0112 against a 0.0005 tolerance (1.1x to 22x): 2 of 5 runs fail on the ROCm
  10.1 runtime, 4 of 5 on 7.2.4, 2 of 5 on the September build with the old compiler and runtime. Not a 10.1 regression.
- **Status:** facts passed to Tom informally (Mark, 11-24); not filed. Everything else (21,203 of 21,204 op tests) passes,
  and the build serves correctly on 10.1. (Its version line, `version: N (sha)`, has no word "commit"; that tripped our
  build gate, not a bug.)
- **Receipt:** `stack-drift/RESULT_ROCM10.md`, `stack-drift/raw/b2_followup.txt`.

## 2026-11-24 -- llama.cpp mainline on gfx1201: one MUL_MAT f16 case over tolerance

- **Where:** ggml-org/llama.cpp `33aeb17f8`, RX 9070 XT (gfx1201), built with ROCm 10.1 (LLVM 24).
- **Shows:** `test-backend-ops -b ROCm0`: 21,002 of 21,003 pass; `MUL_MAT(type_a=f16,type_b=f32,m=16,n=2105344,k=32)`
  error 0.0042 against 0.0005. Same on the 7.2.4 runtime (0.0043), so not the runtime; whether the new compiler is the
  cause is untested (no older build contains this case).
- **Status:** not reported.
- **Receipt:** `stack-drift/RESULT_ROCM10.md`, `stack-drift/raw/b2_followup.txt`.

## 2026-11-23 -- llama.cpp PR #32588 (SenseNova Loop): the head commit shares the loop's full-attention cache

- **Where:** ggml-org/llama.cpp PR #32588 head `0ba8e4adf` (2026-11-22) vs `4bc61eed7`.
- **Shows:** the head reuses the first pass's full-attention KV cache on the second loop pass; SenseTime's reference
  (`modeling_sensenova_loop.py`, `_VisitCache` keyed by execution index) keeps one per pass. Against `4bc61eed7` (which
  reproduces itself 240/240 and matches the reference's perplexity to 0.1 %): 209 of 240 greedy M1 answers differ;
  wikitext perplexity 16.96 vs 16.56.
- **Status:** not reported (facts drafted for Mark, 11-23). Also: the official GGUF uses legacy `mhc.*` keys, which the PR
  still reads.
- **Receipt:** `sensenova-loop/RESULT_SENSENOVA_LOOP.md`.

## 2026-11-23 -- llama.cpp: no architecture summary at the default log level

- **Where:** recent mainline and PR builds (`4bc61eed7`, `33aeb17f8`).
- **Shows:** `print_info` lines (arch, n_layer) no longer appear at the default verbosity; scripts that grep them find
  nothing. Not a bug; read the GGUF header (`sensenova-loop/check_meta.py`) or pass `-lv 4`.
- **Receipt:** `sensenova-loop/PREREG_SENSENOVA_LOOP.md` (Deviation 1).

## Model behaviour worth knowing (not software bugs)

- **Inkling-2-Mini, greedy decoding:** its reasoning can fall into a repetition loop until the token cap (22 of 240 M1
  items at effort "none"); the vendor samples at temperature 1.0. `inkling-mini/RESULT_INKLING_MINI.md`.
- **Qwen3.8 effort "low"** injects a system sentence ("Keep your thinking brief..."); "medium" injects none; "xhigh" a
  longer one. `inkling-mini/PREREG_Q27_LOW.md`, memory note on effort.
