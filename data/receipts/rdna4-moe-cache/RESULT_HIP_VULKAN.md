# MoE expert cache on RDNA4 — HIP doesn't build, and the cache is not numerically neutral

**Branch:** `giveen/llama-cpp-turboquant` @ `8db4887` (behind turboquant PRs #287/#288/#289).
**Hardware:** RX 9070 XT, gfx1201, 16 GiB, discrete (`uma: 0`). ROCm 7.2.4 / RADV (Mesa).
Host 5700X3D, 32 GiB DDR4-3600. **Date:** 2026-08-11.
Prereg: `PREREG_HIP_VS_VULKAN.md`, written before either build.

Jabba built the Vulkan and Metal cache paths and has no hardware to test them.
Tom and Jabba cover CUDA. Defilan's Strix Halo is a *unified-memory* APU, where
the CPU→GPU copy this feature exists to avoid is nearly free. **A discrete AMD
card on PCIe is the regime this feature targets, and nobody else in the group
has one.**

---

## Finding 1 — the CUDA MoE cache does not compile under HIP

`cmake --build build-hip` fails with 6 errors, all in `ggml-cuda/moe-cache.cu`.
Every one is a raw CUDA symbol with no alias in `ggml-cuda/vendors/hip.h`:

```
cudaErrorUnknown                  cudaDeviceGetStreamPriorityRange
cudaErrorInvalidValue             cudaStreamCreateWithPriority
cudaPeekAtLastError  (2 sites)
```

All five are **absent** from `vendors/hip.h`, and clang names the correct HIP
alias for each in its own diagnostic. Because llama.cpp routes AMD through the
CUDA backend via hipify, **this breaks every ROCm user of the CUDA cache path** —
not "slow", not "wrong results": it does not build.

The fix is five `#define` lines in the existing alphabetical block of
`vendors/hip.h`. It belongs in the shim, not in `moe-cache.cu`: the new code uses
ordinary CUDA APIs that simply had not been needed before, so fixing the shim
covers any future file too.

```c
#define cudaDeviceGetStreamPriorityRange hipDeviceGetStreamPriorityRange
#define cudaErrorInvalidValue            hipErrorInvalidValue
#define cudaErrorUnknown                 hipErrorUnknown
#define cudaPeekAtLastError              hipPeekAtLastError
#define cudaStreamCreateWithPriority     hipStreamCreateWithPriority
```

With those applied: **HIP builds clean, 0 errors**, `llama-server` and
`llama-bench` produced, device enumerates as
`AMD Radeon RX 9070 XT, gfx1201, Wave Size: 32, 16304 MiB`.

**Vulkan built clean with no source changes at all.** The untested backend
compiled; the "known good" one did not.

## Finding 2 — the cache changes generated text at temp 0 (P7 falsified)

Greedy, `--temp 0 --seed 1234`, identical prompt, identical harness, 96 tokens,
`-ngl 99 --cpu-moe`, HIP.

**Both arms are individually deterministic** — this was verified first, because
`agent-benchmark-determinism` records that temp-0 runs are not always reproducible
on this fleet:

| arm | run B vs run C |
|---|---|
| `--moe-cache off` | **byte-identical** |
| `--moe-cache 4096` | **byte-identical** |

**Repacking was then held constant**, because `arg.cpp` disables weight repacking
for `MODE_ON` (which a numeric budget sets) but not for `off`:

| comparison | repacking | result |
|---|---|---|
| `off` vs `off --no-repack` | varies | **no content change** (trailing escape only) |
| `off --no-repack` vs `4096` | **held off** | **content differs** |

```
- ... instead of one large dense layer
+ ... instead of one big   dense layer
```

The divergence reproduced across three independent comparisons. **With repacking
controlled and both arms deterministic, enabling the expert cache changes the
generated token stream.**

A residency cache should be numerically neutral — it decides *where* a weight
lives, not what it is. A one-token divergence in 96 is a small effect, but
non-zero is the claim: the cached path does not produce bit-identical logits.
Whether that is a bug or an accepted consequence of a different dequant or
accumulation path is the author's call. Two consequences either way:

1. It cannot be assumed safe for anyone who needs reproducible output.
2. **A/B benchmarks across cache modes are not comparing the same computation.**

## Finding 3 — Vulkan works, and it is the control that indicts the HIP path

The Vulkan MoE cache **runs**: exit 0 on every attempt, no crash, no validation
error, and byte-identical across repeat runs. **P3 confirmed** — the backend the
author could not test is functional.

More importantly, running Finding 2's exact test on Vulkan inverts the result:

| backend | `off --no-repack` vs `--moe-cache 4096` |
|---|---|
| **HIP** (gfx1201, ROCm 7.2.4) | **DIFFERS** — generated text changes |
| **Vulkan** (RADV gfx1201) | **IDENTICAL** |

Same card, same model, same prompt, same seed, same harness, repacking held
constant on both sides, both backends individually deterministic.

**This is what turns Finding 2 from an observation into a defect report.** If a
residency cache were inherently non-neutral — a consequence of a different
dequant or accumulation path that any implementation would share — both backends
would diverge. Only the CUDA/HIP one does. The Vulkan implementation demonstrates
that byte-identical caching on this hardware is achievable, so the HIP path's
divergence is a property of that implementation, not of the idea.

HIP and Vulkan disagree with **each other** at temp 0, which is expected and not
a finding: different kernels, different accumulation order.

## Not established

- **Throughput is unmeasured, and an earlier +36% claim from this session is
  withdrawn.** It was a page-cache artifact: a 19.7 GiB mmap'd model on a 32 GiB
  host, first arm cold, second warm. Interleaved reruns gave `off` 19.7 / 18.0
  and `4096` 12.0 / 15.4 t/s — within-arm spread larger than the effect. Any real
  number needs cache-state control and interleaved reps. **P4 and P6 remain open.**
- **P5 (HIP vs Vulkan throughput) untested.**
- CUDA is not tested here — no NVIDIA card in this box. Finding 2 may or may not
  apply to CUDA; it is a claim about the HIP path only.

## Prediction scoring so far

| ID | Prediction | Conf | Outcome |
|---|---|---|---|
| P1 | HIP builds without source edits | 0.75 | ❌ **FALSIFIED** — 5 missing aliases |
| P2 | Vulkan builds without source edits | 0.80 | ✅ confirmed |
| P3 | Vulkan cache runs without crashing | 0.50 | ✅ **CONFIRMED** — exit 0, deterministic |
| P4 | `N` beats `off` by ≥15% TG | 0.70 | — unmeasured (confounded) |
| P5 | HIP beats Vulkan by ≥20% TG | 0.65 | — untested |
| P6 | Jabba's +30–50% doesn't reproduce | 0.60 | — unmeasured |
| P7 | output byte-identical across cache modes | 0.70 | ❌ **FALSIFIED on HIP**, ✅ holds on Vulkan |

## Method notes

- Two backends built from the **same commit** of the same clone (gate G3).
- **Correctness before throughput** (gate G2) is why Finding 2 exists at all.
- The first invocation OOM'd: `--moe-cache` manages expert *residency*, it does
  not do placement. `-ngl 99` still allocates every layer on device. The cache is
  a companion to `--cpu-moe`, not a substitute for it.
- **Do not copy `--no-mmap`** from CUDA testers' command lines onto a 32 GiB host
  with a 20 GiB model.
