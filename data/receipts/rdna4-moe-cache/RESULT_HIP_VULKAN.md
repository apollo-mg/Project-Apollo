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

---

# RETEST @ `1131bbe` — "cuda: fix HIP MoE cache compatibility and q8_1 sums"

Jabba pushed a fix and asked for a re-run. Pulled, reset to clean upstream
(my local patch discarded), rebuilt **both** backends at the new commit.

## Finding 1 is FIXED

All five aliases are now in `vendors/hip.h`, `#ifndef`-guarded. **HIP builds
clean with zero source edits** — P1 now passes upstream. Vulkan unchanged.

The commit also carries a real numerics fix in `quantize.cu`:

```c
- float sum = xi;                            // sum of ORIGINAL float activations
- sum = warp_reduce_sum<QK8_1>(sum);
+ sum = warp_reduce_sum<QK8_1>((float) q);   // sum of QUANTIZED int8 values
- y[ib].ds = make_half2(d, sum);
+ y[ib].ds = make_half2(d, d * sum);
```

`ds.y` carries the activation sum that corrects asymmetric weight quantization
in the integer dot product. Since the dot product consumes the *quantized*
activations, the sum must be `d·Σq`; the old `Σx` carried the quantization
residual as error. Correct fix, and it affects all CUDA/HIP inference, not just
the cache.

## Finding 2 is NOT fixed — and the evidence is now much sharper

Same test at `1131bbe`. Both HIP arms still individually deterministic. The
divergence is **unchanged, at the same token**.

Running all four arms at the same commit isolates it completely:

| arm | divergent token |
|---|---|
| HIP `--moe-cache off --no-repack` | one **large** dense layer |
| **HIP `--moe-cache 4096`** | **one big dense layer** |
| Vulkan `--moe-cache off --no-repack` | one **large** dense layer |
| Vulkan `--moe-cache 4096` | one **large** dense layer |

**Three of four agree; the HIP cached path is the singleton.** It disagrees with
its own cache-off arm *and* with both Vulkan arms. Vulkan remains byte-identical
across cache modes (`IDENTICAL`, control holds at the new commit).

HIP and Vulkan differ from each other elsewhere in the text — expected, different
kernels — but at this token three arms converge and only HIP-with-cache does not.
That rules out "backends just differ" as the explanation.

**Conclusion unchanged and strengthened: the CUDA/HIP expert-cache path is not
numerically neutral, the Vulkan one is, and the q8_1 fix did not close it.**

## Scoring update

| ID | Conf | @ 8db4887 | @ 1131bbe |
|---|---|---|---|
| P1 | 0.75 | ❌ needed 5 aliases | ✅ **fixed upstream** |
| P2 | 0.80 | ✅ | ✅ |
| P3 | 0.50 | ✅ | ✅ |
| P7 | 0.70 | ❌ on HIP / ✅ Vulkan | ❌ **still on HIP** / ✅ Vulkan |

P4/P5/P6 remain unmeasured — throughput is still page-cache confounded and no
number from this box should be quoted.

---

# CORRECTION — the placement regime was wrong, and it changes the headline

Jabba: *"try a model bigger than your VRAM, that's where this lands."* He was
right, and my configuration was measuring the feature outside its intended regime.

`-ngl 99 --cpu-moe` pins **every** expert to CPU. That leaves VRAM headroom and
nothing for the cache to relieve. His shape is `-ngl auto --fit on`, which lets
the fitter place what it can and the cache absorb the overflow.

## Throughput, both regimes, same 19.7 GiB model on a 16 GiB card

| placement | `--moe-cache off` | `--moe-cache auto` |
|---|---|---|
| `-ngl 99 --cpu-moe` (mine, wrong regime) | 18.0 t/s | 15.4 t/s (cache slightly *slower*) |
| **`-ngl auto --fit on`** (his, correct) | **0.4 t/s** | **19.3 / 17.0 t/s** |

**~45×.** Not the +30–50% reported on CUDA — in this regime the alternative is
thrashing, so the cache is the difference between unusable and usable. A gap that
size also makes the page-cache confound irrelevant, which is why this is the first
throughput number from this box worth quoting.

**P4 confirmed** (`N` beats `off` by ≥15%) — overwhelmingly.
**P6 falsified** — I predicted Jabba's magnitude would *not* reproduce here. It
didn't: it is far larger, not smaller.

## Two prior characterisations of mine were wrong

1. **"`--moe-cache off` crashes."** It does not. `terminate called without an
   active exception` with a `std::thread` destructor came from `timeout` sending
   SIGTERM during teardown — an artifact of my own kill, not the program.
2. **"It hangs / 0.0 t/s."** Also wrong. With `-n 4` it exits 0 in 278 s at
   **0.4 t/s**. The zeros were 96 tokens at that rate overrunning my timeout.

The real behaviour is simply catastrophic slowness without the cache, which is
the feature working as designed.

## What this does to Finding 2

The P7 divergence was measured under `-ngl 99 --cpu-moe` — a configuration this
feature is not meant to be used in. It remains a real, reproduced, controlled
result **for that configuration**, with the Vulkan arm as its control. Whether it
also appears under `-ngl auto --fit on` is **untested**: comparing outputs there
needs a cache-off arm, and cache-off costs ~70 s per token. Scope the claim
accordingly — it is not established for the regime users will actually run.

---

# PASCAL (sm_60) — builds, but engagement never confirmed

`.194`, Tesla P100-PCIE-16GB, **compute capability 6.0**, CUDA 12.4, driver 580.173.02,
`CUDA_VISIBLE_DEVICES=0` (one card, 16269 MiB) vs a 23.92 GiB Q6_K MoE
(`Hermes3.6-35B-A3B-...-APEX`, experts Q5_K x80 / Q6_K x39 / Q8_0 x1 — all supported
by the CUDA path, which covers 23 types).

## What is established

**1. `moe-cache.cu` compiles for sm_60 — 0 errors.** `-DCMAKE_CUDA_ARCHITECTURES=60`,
CUDA 12.4, host gcc 13.4. So the CC floor is a **policy decision at session
creation**, not a compilation constraint. There is no kernel-level cc gate in the
file; the only check is the device skip at `moe-cache.cu:1572`.

**2. Forcing the floor changes nothing measurable.** `GGML_CUDA_MOE_CACHE_MIN_CC=600`
lets cc 600 pass the gate. Default vs forced, r=1:

| arm | `--moe-cache auto` | `--moe-cache 4096` |
|---|---|---|
| default (gate active) | pp32 24.46 / tg8 17.36 | pp32 21.66 / tg8 8.47 |
| forced MIN_CC=600 | pp32 24.82 / tg8 17.44 | pp32 21.64 / tg8 9.15 |

**3. The explicit-mode repacking penalty is real and large.** `llama-bench` grew a
`repack` column reading **off** for the explicit budget, confirming `arg.cpp:839`.
In the `-ncmoe` regime that costs **~2x on tg — 17.4 to 8.5 t/s** — because every
expert is on CPU, so CPU-side weight repacking is doing most of the work. Anyone
comparing `auto` against an explicit budget in this regime is mostly measuring
repacking, not caching.

## What is NOT established — gate G4 fails

**No `[moe-cache]` log line appeared in any arm**, forced or not, despite
`MOE_CACHE_LOG` mapping straight to `GGML_LOG_INFO` and other INFO lines (the
device banner) printing normally. So **the cache was never confirmed to engage on
Pascal at all.** This cannot distinguish "forced cache ran and did not help" from
"forced cache still did not initialise". Per this receipt's own G4, *"it ran and
nothing crashed" is not evidence the feature was exercised* — so the Pascal
question remains open, not answered.

Likely explanation worth chasing: `auto` may require a fit target to select the
cache at all (`common_moe_cache_evaluate_fit()` sets `fit_selected`), which would
also retroactively explain the `-ncmoe` nulls on RDNA4 and on Defilan's Strix.

## Correction

An earlier reading of this run as "CPU inference, the GPU was never used" was
**wrong**. `llama-cli`'s TUI suppresses `GGML_LOG_INFO`, so the absence of device
lines was a logging artifact. `llama-bench` shows `backend CUDA` and the P100
banner. The 26.4 t/s figure was GPU.

---

# RESOLVED @ `bb3c3fa` — every null was the same bug in our protocol

Jabba added logging at the silent failure points. It immediately explains three
independent null results, including two of mine.

## The cache in `auto` mode is selected by the FIT EVALUATOR

With `-fitt` (fit target), RDNA4 finally speaks:

```
common_params_fit_impl: MoE cache fit selected main-device dense placement with
  10114 MiB projected cache capacity for 18600 MiB of routed expert weights
  (up to 54.4% coverage)
```

Without a fit target — plain `-ncmoe N --moe-cache auto` — **no fit evaluation runs,
the cache is never selected, and toggling `--moe-cache` changes nothing.**

That is the whole explanation for:

- Defilan's Strix Halo null (he hedged it as a UMA artifact — it was not)
- My RDNA4 `-ncmoe 41` null (both orderings, BigBang)
- My earlier `--cpu-moe` result where the cache looked *slower*
- The Pascal runs showing no log lines at all

**Every one of those A/Bs toggled a flag that did nothing.** Defilan was closest —
he warned that `common_moe_cache_evaluate_fit()` can set `fit_selected`, and that
toggling `--moe-cache` with `--fit` may not isolate it. The inverse turned out to
matter more: toggling it *without* fit isolates nothing because nothing is on.

## Pascal: the CC gate is bypassable, coverage is the real blocker

One P100 (cc 6.0, 16269 MiB) vs a 23.92 GiB Q6_K MoE, `-fitt 1024`:

| arm | fit evaluator says |
|---|---|
| default | `no selected device satisfies the cache hardware policy` |
| `GGML_CUDA_MOE_CACHE_MIN_CC=600` | `some routed expert weights would remain permanently uncached` |

**The reason changes, which proves the override works** — cc 600 clears the hardware
gate. The cache then still declines, on a different policy: it will not accept
partial coverage here. RDNA4 accepted 54.4% coverage on a 19.7 GiB model, so the
threshold is coverage-dependent rather than a flat rule.

So the answer to *"does the MoE cache work on Pascal?"* is: **the hardware gate is
not the binding constraint — VRAM coverage is.** `.194` cannot demonstrate it either
way, because 1 card is too little coverage and 4 cards (64 GiB) fit the whole model
with no CPU-resident experts left to cache.

## The 45x survives reversal

Ordering reversed, `-ngl auto --fit on`, identical settings, RDNA4:

| arm | position | result |
|---|---|---|
| `--moe-cache off` | first | did not finish 8 tokens in 280 s |
| `--moe-cache auto` | second | 4.8 t/s |
| `--moe-cache auto` | **first** | 5.2 t/s |
| `--moe-cache off` | **second** | did not finish 8 tokens in 280 s |

**The effect follows the arm, not the position.** `auto` completes in both positions
within 8% of itself; `off` fails to produce 8 tokens in 280 s in both. The
usable/unusable split is real and reproduces reversed.

The *magnitude* is not established: at `-n 8` warm-up dominates and `auto` reads
~5 t/s against the 19.3 t/s measured at `-n 96 -c 2048`. Quote the qualitative
result, not "45x".

---

# FINAL @ `bb3c3fa`, using the documented recipes — the win is PLACEMENT, not caching

Ran both benchmark recipes from `docs/backend/MOE-CACHE.md`, with the two controls
that were missing all day: `--n-gen-warmup` (his doc: *"pool creation waits for
graph-shape discovery, expert admission needs repeated demand"*) and `--repack off`
pinned on **both** arms.

## Regime A — `-ncmoe` + fixed budget: NO reliable effect

`-ngl 99 -ncmoe 40 --repack off --n-gen-warmup 64 -r 3`, tg128:

| ordering | first arm | second arm |
|---|---|---|
| `off,4096` | off **19.07 ± 3.22** | 4096 **33.85 ± 3.71** |
| `4096,off` | 4096 **16.67 ± 3.17** | off **19.88 ± 5.72** |

**The second arm wins both times.** The `4096` config swings **2.0x on position
alone** (33.85 vs 16.67); `off` is stable across positions (19.07 vs 19.88, 4%).

A `+77%` reading from the forward ordering is **withdrawn**. With ordering
controlled there is no measurable cache benefit in this regime — which *confirms*
rather than contradicts the three earlier nulls (Defilan's Strix, my RDNA4, my
Pascal). They were right for the wrong reason: the dead `-ncmoe`+`auto` combination
explained why they saw nothing, but even the *live* fixed-budget path shows nothing
here.

## Regime B — `-fitt` + `auto`: large effect, and the evaluator says why

`-ngl 99 -fitt 1024 --n-gen-warmup 16 -r 1`, tg48:

```
MoE cache fit selected main-device dense placement with 9934 MiB projected cache
  capacity for 18600 MiB of routed expert weights (up to 53.4% coverage)

off   0.98 t/s        auto  5.76 t/s        5.9x
```

Supported by the earlier reversal at `-n 8`, where the effect followed the **arm**:
`auto` completed in both positions (5.2 first, 4.8 second) while `off` failed to
produce 8 tokens in 280 s in both.

## The conclusion these two regimes force

**The benefit comes from cache-aware *placement*, not from caching a
user-fixed placement.** With `-ncmoe` the user has already decided where experts
live and the cache is a bolt-on — no reliable gain. With `-fitt` the fit evaluator
*chooses a different placement* built around the cache, and that is where the large
win lives. The doc says exactly this — *"cache-aware fit ... choosing between stock
and cache placement"* — but the distinction is easy to miss, and every tester in the
channel (me included) defaulted to `-ncmoe`.

**Practical guidance worth putting in the PR, not just the doc:**
- `-ncmoe` + `--moe-cache auto` is a dead combination — `-ncmoe` is authoritative and
  blocks fit, `auto` requires fit. It silently measures nothing.
- Any A/B without `--n-gen-warmup` measures warm-up, not the cache.
- Any A/B without reversed ordering measures position. Observed swings today:
  3.9x (pp) and 2.0x (tg) on **identical configs**.

## Still open

The numerical divergence stands and is unaddressed by the doc: on HIP the cached
path produced different tokens than cache-off at temp 0 with repacking held
constant, while Vulkan was byte-identical under the same test. The doc describes
opportunistic residency management, which should be numerically neutral by
construction. It neither claims bit-exactness nor documents its absence.

---

# 2026-08-12 — RETRACTION AND ROOT CAUSES

Everything above the line was written before three things were checked: whether
the caches in each arm ever *engaged*, what the author's updated doc says about
bit-exactness, and why Pascal produced a null. All three are now settled, and one
of them retracts the strongest claim in this document.

## Retraction 1 — Finding 3 is FALSIFIED. The Vulkan cache never ran.

`llama-cli` suppressed `GGML_LOG_INFO`, and the Vulkan binary used for the
original control was built at 12:27, **before** `bb3c3fa` added engagement
logging. So no arm in this document — HIP or Vulkan — ever printed a single
engagement or hit counter. The Vulkan control was never verified; it was assumed.

Re-run at `bb3c3fa` with `-lv 4`, stdout (tokens) split from stderr (diagnostics):

```
vk_4096: llama_model_has_cacheable_moe_weights: MoE cache disabled (no provider registered)
```

**Root cause, in the source, not the configuration:**

```c
// ggml/src/ggml-vulkan/ggml-vulkan.cpp:19035, inside ggml_backend_vk_reg()
#ifdef GGML_USE_VULKAN
        ggml_vulkan_moe_cache_register(&reg);
#endif
```

The CMake option is `GGML_VULKAN`. `GGML_USE_VULKAN` is defined **nowhere** in the
build system, and the `ggml-vulkan` target's `CXX_DEFINES` does not contain it.
The registration call is compiled out. `ggml_vulkan_moe_cache_register` is present
and exported in `libggml-vulkan.so` (`T`), and the Vulkan cache kernels
`moe_cache_mv_{q4_0,q4_K,q6_K,q8_0}` are compiled in — all of it unreachable.

**The Vulkan MoE cache is dead code in any standard `-DGGML_VULKAN=ON` build.**

Consequences for claims made in this document:

| claim | status |
|---|---|
| "Vulkan MoE cache works, exit 0, no validation error" | **vacuous** — it ran ordinary inference with no cache |
| "Vulkan is byte-identical across cache modes" | **vacuous** — both arms were cache-off |
| "Vulkan is the control that indicts the HIP path" | **RETRACTED** — there was no control |
| "UD-Q8_K_XL is 100% MXFP4, Vulkan has no such kernel" | conclusion (it won't cache) accidentally right, **mechanism wrong** — Vulkan has cache kernels; none are reachable |

The doc states *"the CUDA, HIP, Metal, and Vulkan backends register a provider."*
As built, Vulkan does not.

## Retraction 2 — Finding 2's *interpretation* was wrong. The observation stands.

I argued a residency cache "should be numerically neutral — it decides *where* a
weight lives, not what it is." The author's `d0fe73b` documents otherwise:

> *"Output can differ slightly from CPU output because the hit path uses
> activation quantization and matvec arithmetic on the backend. Do not expect
> bit-identical logits or token streams. In particular, a small rounding
> difference can change a near-tie greedy token."*

A hit does not relocate a weight, it **moves the computation** from the stock CPU
path to a backend matvec on quantized activations. Divergence is the mechanism
working as designed. **Not a defect.** With the Vulkan control gone, nothing
indicts the HIP path — and there was never anything to indict.

The *observation* is now better supported than when it was a defect claim.
Re-run at `bb3c3fa`, repacking pinned off both sides, clean exit, engagement and
hit counters proven on the same run:

```
[moe-cache] CUDA0 pool[0]: type=q4_K expert=576 KiB entries=25600 coverage=partial
[moe-cache] enabled: first pool allocated on CUDA0
[moe-cache] CUDA0 pool[1]: type=q6_K expert=840 KiB entries=5120 coverage=partial
[moe-cache] CUDA0 hits=62889/95056 (66.2%) used=6742/6742 fill-fail=0
            evictions=119 dispatch-fail=0 collect-fail=0 bypass=0
```

Entry counts match the model census exactly (100 `Q4_K` x 256 experts = 25600;
20 `Q6_K` x 256 = 5120). Divergence reproduces at the same token as before:

```
- ...instead of one large dense layer
+ ...instead of one big   dense layer
```

## Root cause 3 — the Pascal null was a size threshold, not the hardware

`b2fd919` recorded that sm_60 "builds, but engagement never confirmed." It is now
confirmed, and the blocker was never compute capability alone. Two gates in series:

```c
moe_cache_cc_forced_min               = 700;        // device gate
moe_cache_expert_bytes_ampere_min     = 512u << 10; // 512 KiB,  cc >= 800
moe_cache_expert_bytes_pre_ampere_min = 1u << 20;   // 1024 KiB, cc <  800
```

`GGML_CUDA_MOE_CACHE_MIN_CC=600` clears the first gate. The second then rejects
every expert tensor: **qwen35moe `Q6_K` experts are 840 KiB, and the pre-Ampere
default demands 1024 KiB.** The probe reports:

```
MoE cache disabled (no cacheable expert tensors found)
```

which is misleading — the tensors are fine; a device-class default excluded them.
Discriminated by running the same model on gfx1201, where it engages, so the null
is architectural rather than a property of the model. With both overrides:

```
GGML_CUDA_MOE_CACHE_MIN_CC=600 GGML_CUDA_MOE_CACHE_MIN_EXPERT_KB=512
[moe-cache] CUDA0 pool[0]: type=q6_K expert=840 KiB entries=30720 coverage=partial
[moe-cache] enabled: first pool allocated on CUDA0
```

**First confirmed MoE cache engagement on Tesla P100 / sm_60**, same pool geometry
as gfx1201. Note this only clears the *eligibility* gates — whether the sm_60 hit
path is profitable or numerically sane is a separate question, measured next.

## Finding 4 — the divergence is NOT HIP-specific. It reproduces on real CUDA.

This was the question `.194` existed to answer, and it is the reason the HIP-only
result could never settle it: HIP compiles the *same* `moe-cache.cu` through the
hipify vendor header, so "HIP-specific" was an assumption, not a measurement.

Tesla P100 / sm_60, CUDA 12.4, single card (`CUDA_VISIBLE_DEVICES=0`), Darwin-36B
`Q6_K`, `-ngl 99 --cpu-moe` so the model exceeds the 16 GB card, `--temp 0
--seed 1234`, repacking pinned off on the cache-off arm, both overrides set,
build at `bb3c3fa` — the same commit as the HIP and Vulkan builds.

```
[moe-cache] enabled: first pool allocated on CUDA0
[moe-cache] CUDA0 pool[0]: type=q6_K expert=840 KiB entries=30720 coverage=partial
[moe-cache] CUDA0 hits=56569/95056 (59.5%) used=4990/4990 fill-fail=0
            evictions=1045 dispatch-fail=0 collect-fail=0 bypass=0
```

Token stream: **DIFFERS**. Prediction logged before the run was 0.6 that CUDA
would diverge; it does.

Both backends that share the CUDA implementation diverge; the one backend that did
not diverge turned out never to have run its cache at all. Combined with the
author's documented mechanism — the hit path uses activation quantization and
backend matvec instead of the stock CPU path — the picture is consistent and
unremarkable: **this is what the design does, on every backend that implements it.**

Do not compare the *magnitude* of the HIP and CUDA divergences from these runs.
They used different models (Qwopus `Q4_K`+`Q6_K` vs Darwin `Q6_K`), and once any
token differs the remainder of a greedy generation diverges downstream, so a
divergence that starts earlier looks larger for reasons that have nothing to do
with the backend.

Throughput on the cached arm looked better (11.5 -> 18.0 t/s) but that is a single
unreversed ordering and is **not claimable** — reversal is running. Today's own
blocked-ordering swings on identical configs were 3.9x (pp) and 2.0x (tg).

## Method failures worth keeping

Four defects in this document trace to two habits, both now fixed:

1. **`llama-cli` ignores `-no-cnv` and parks at an interactive prompt.** Every arm
   ran to its `timeout` instead of exiting. Teardown statistics — the hit counters
   that constitute engagement proof — print only at exit, so no arm ever emitted
   them. Fix: `< /dev/null`. This also produced two false "crash" reports, since a
   `timeout` SIGTERM and a task kill both surface as a gdb backtrace.
2. **Engagement treated as a footnote instead of a gate.** A disabled cache and a
   numerically-neutral cache are indistinguishable from the token stream alone.
   Every cache claim now requires `[moe-cache] enabled` **plus nonzero hits** from
   the same run that produced the tokens.

Also: diff the generated text only. Raw stdout carries a load spinner whose length
tracks model-load time, and a throughput footer that varies by construction —
either will read as divergence. `hip_4096` looked 4x larger than `hip_off` from
spinner alone, and the first Pascal comparison reported "DIFFERS" on the t/s line
while the generated text was identical.
