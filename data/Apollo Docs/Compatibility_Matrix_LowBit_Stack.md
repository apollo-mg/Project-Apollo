# Compatibility Matrix — the low-bit stack doesn't compose

**Measured 2026-07-20** against the actual source trees on disk, not documentation.

## The problem in one sentence

The people most likely to want a 2-bit 27B are scraping for VRAM, which means they also need
quantized KV cache and speculative decoding to make it usable — and **those three features live
in three mutually incompatible forks that have collided on the same GGML type numbers.**

## The collision

`GGML_TYPE_*` numbering, read from `ggml/include/ggml.h` in each tree:

| type | upstream `ggml-org` | `spiritbuun/buun-llama-cpp` | `llama-cpp-turboquant` (TheTom) |
|-----:|---------------------|------------------------------|----------------------------------|
| 41 | `Q1_0` | `Q1_0` | `Q1_0` |
| **42** | **`Q2_0`** ← Bonsai weights | `TURBO3_0` (3-bit KV) | `TURBO2_0` (2-bit KV) |
| 43 | *COUNT* | `TURBO4_0` | `TURBO3_0` |
| 44 | — | `TURBO2_0` | `TURBO4_0` |
| 45 | — | `TURBO3_TCQ` | `TQ3_1S` (3-bit **weights**) |
| 46 | — | `TURBO2_TCQ` | `TQ4_1S` (4-bit **weights**) |
| 47 | — | `TURBO8_0` | *COUNT* |

Three observations:

1. **Type 42 means three different things.** A Bonsai GGUF loaded into either TurboQuant fork has
   its weight type read as a KV-cache format.
2. **buun and TheTom have TURBO2_0 and TURBO3_0 swapped.** These two forks are not compatible with
   each other either. This is not academic — buun's tree persists KV checkpoints to a sidecar file
   for slot save/restore, so a cache written by one fork is misread by the other.
3. Neither TurboQuant fork defines `Q2_0` at all.

## Feature availability

| capability | upstream | PrismML | buun | TheTom |
|---|---|---|---|---|
| Bonsai `Q2_0` weights — CPU | ✅ ref impl in `ggml-quants.c` | ✅ + AVX512-VNNI fast path | ❌ | ❌ |
| Bonsai `Q2_0` weights — CUDA | ❌ **zero refs in `ggml-cuda/`** | ✅ native | ❌ | ❌ |
| Bonsai `Q2_0` — Metal / Vulkan / HIP | ❌ | ✅ (HIP+Vulkan shipped as prebuilt bundles) | ❌ | ❌ |
| MTP speculative decode | ✅ `draft-mtp` | ✅ (inherited) | ✅ | ✅ |
| DSpark speculative decode | ❌ | ✅ requires fork server code | ❌ | ❌ |
| TurboQuant KV cache | ❌ | ❌ | ✅ TURBO2/3/4/8 + TCQ | ✅ TURBO2/3/4 |
| TurboQuant *weight* quants | ❌ | ❌ | ❌ | ✅ TQ3_1S, TQ4_1S |
| VBR KV cache | ❌ | ❌ | ✅ | ❌ |
| Standard KV quant | Q4_0/Q4_1/Q5_0/Q5_1/Q8_0 | same | same + turbo | same + turbo |

**MTP is the good news: it is upstream.** `draft-mtp` is in ggml-org's `common/speculative.cpp`,
so multi-token prediction is the one accelerator on this list nobody has to fork for.

## What you cannot currently do

- **Bonsai + TurboQuant KV on one build.** The single most wanted combination for a 16GB card is
  the one blocked by the type-42 collision. Resolving it means renumbering in one of the trees.
- **Bonsai + DSpark on a non-PrismML build.** DSpark is not a plain draft model. The fork's
  commits (`wire dspark tap capture`, `fix/dspark-unmasked-capture`) show it taps internal state
  from the target model, EAGLE-style, and needs server-side support that exists nowhere else.
- **Bonsai on any GPU with stock llama.cpp.** Upstream has the type and a CPU reference
  implementation but **no CUDA kernels at all**, so `-ngl` offload has nothing to call.

## What is changing, and fast

PrismML's fork carries branches named `pr/q2_0-cpu`, `pr/q2_0-cuda`, `pr/q2_0-metal`,
`pr/q2_0-vulkan`, `pr/q2_0-x86`. They are upstreaming Q2_0 across every backend, and the CPU leg
has evidently already landed — which is exactly why upstream has `dequantize_row_q2_0` but an
empty `ggml-cuda/`. 373 stars, pushed the same day this was written.

**Implication for the type collision: it gets worse before it gets better.** Every backend PR that
lands makes `Q2_0 = 42` more entrenched upstream, and the two TurboQuant forks are the ones that
will have to move. Whoever renumbers first has an easier merge.

No `pr/dspark-*` branch exists. Q2_0 is on a path to everyone; DSpark is not.

## Practical guidance

| you want | build to use | cost |
|---|---|---|
| Bonsai on a GPU, today | PrismML fork (or their prebuilt HIP/Vulkan bundle) | no TurboQuant KV |
| Long context on 16GB | buun or TheTom | no Bonsai |
| MTP | anything, including upstream | — |
| Bonsai + long context | **not currently possible in one build** | — |

## Open items

- Untested: whether upstream's CPU-only `Q2_0` path will actually load a Bonsai GGUF and
  generate. The enum and dequant exist; that is not the same as working inference. Cheap to check.
- Untested: DSpark acceptance rate on non-H100 hardware. Prism ML claims τ ≈ 3.7 at depth 4 for
  1.34× on H100. Our own MTP work shows acceptance-to-throughput translation is strongly
  hardware-dependent — on bandwidth-bound Pascal, MTP returned 1.57–1.77× where a 5090-calibrated
  rule of thumb predicted it would not pay at all.
- Unknown: whether Prism ML intends to upstream DSpark, and whether the TurboQuant forks intend to
  renumber.
