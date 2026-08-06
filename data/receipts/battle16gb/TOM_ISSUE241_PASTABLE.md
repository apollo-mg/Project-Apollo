# Pastable — turboquant issue #241 (turbo3 V-cache corruption)

For Mark to post to https://github.com/TheTom/llama-cpp-turboquant/issues/241
Receipt: `TURBO3_ISSUE241_POLARIS_REPRO.md`. All numbers verified; provenance at bottom of that file.

---

## Reproduced on RX 580 / Polaris10 / RADV — deterministically

I can confirm @suhermanme's report, and I think I can narrow it usefully.

**Setup:** RX 580 8GB (Polaris10, GCN4), Vulkan/RADV, CachyOS, turboquant **9971 (`c26cbdffc`)**
self-built. Crow-9B (Qwen3.5, IQ4_XS), `-c 16384 -b 1024 -ub 512 -fa on -np 1 -ngl 99
--cache-ram 0`, temp 0, `cache_prompt:false`, their prompt ("Write a 500-word essay about Linux.").

Gate is gzip compression ratio of the output — degenerate repetition compresses far better than
healthy prose — plus reading the text.

| K / V | gzip ratio | verdict |
|---|---|---|
| f16 / f16 | **0.5097** | correct (control) |
| turbo4 / turbo4 | **0.5024** | correct |
| turbo4 / turbo2 | **0.5021** | correct |
| **turbo4 / turbo3** | **0.2736** | **CORRUPT** ← your reported pair |
| **turbo3 / turbo3** | **0.3474** | **CORRUPT** |
| **f16 / turbo3** | **0.1753** | **CORRUPT** |

Non-turbo3 cells cluster at 0.502–0.510. Every turbo3-V cell is 0.175–0.347. No overlap.

**Ran the whole matrix twice, fresh server per cell — all six cells byte-identical across runs.**
So this is a deterministic repro, not an intermittent one; you should get the same bytes.

### What the corrupt cells actually emit

Controls all correctly read the prompt:
> `1. **Analyze the Request:** * **Topic:** Linux. * **Format:** Essay. * **Length:** ~500 words.`

**turbo4/turbo3** invents a persona that is nowhere in the prompt:
> *"The user wants an essay about Linux written in the style of a specific persona. The persona is
> a "tall, lanky guy in his late teens" who's "scrawny as a rail"…"*

**turbo3/turbo3** can't see the prompt at all:
> *"the prompt is just a single word: "SS""*

**f16/turbo3** degenerates into a loop — same failure class as the CJK punctuation in the original
report, just English tokens because it's a different model:
> *"The essay below is about the impact of open-source software on the tech industry… *** The
> essay below is about the impact of open-source software on the tech industry…"*

## Two things this isolates

**1. It's the V side.** `f16` K + `turbo3` V still fails, and fails worst. K compression is
irrelevant.

**2. It's Polaris/GCN4, not the codec and not Vulkan.** Same commit, same six cells, same script:

| hardware | backend | result |
|---|---|---|
| RX 9070 XT (RDNA4) | HIP/ROCm | 6/6 healthy |
| RX 9070 XT (RDNA4) | **Vulkan/RADV** | **6/6 healthy** |
| **RX 580 (Polaris10)** | **Vulkan/RADV** | **3/3 turbo3 cells corrupt** |

The RDNA4 **Vulkan** row is the important one — RADV itself is fine there, so this isn't "the
Vulkan turbo3 path is broken," it's GCN4 specifically.

**Non-monotonicity is the tell:** turbo2 (more compressed) works, turbo4 (less compressed) works,
turbo3 in between is broken. A precision/quality tradeoff degrades monotonically; a hole in the
middle of the ladder is a bug.

## Hypothesis — offered as a code-reading lead, not something I've instrumented

turbo3_0 is **the only turbo block with two trailing `uint8_t` arrays**:

```glsl
struct block_turbo2_0 { float16_t norm; uint8_t qs[32]; };              // 34 B
struct block_turbo4_0 { float16_t norm; uint8_t qs[64]; };              // 66 B
struct block_turbo3_0 { float16_t norm; uint8_t qs[32]; uint8_t signs[16]; };  // 50 B
```

The C++ side asserts a packed 50 bytes:

```cpp
static_assert(sizeof(block_turbo3_0) == sizeof(ggml_half) + QK_TURBO3/4 + QK_TURBO3/8,
              "wrong turbo3_0 block size/padding");
```

so `signs` must begin at byte 34. turbo2 and turbo4 have no second array, so no second offset is
ever computed — which matches exactly which codecs work.

The dequant reads the 3-bit index from the two arrays separately:

```glsl
const uint low2 = (uint(data_a[ib].qs   [j / 4]) >> ((j % 4) * 2)) & 0x3;
const uint hi1  = (uint(data_a[ib].signs[j / 8]) >> ( j % 8     )) & 0x1;
const uint idx  = low2 | (hi1 << 2);
```

**If the GCN4 compiler places `signs` anywhere other than offset 34** — e.g. padding it to 36 —
every high bit comes from the wrong byte, so half the centroid indices are wrong, every block,
every token. That would produce exactly this: V values quietly wrong, context becoming noise,
output either hallucinated or looping, while K-side codecs are unaffected.

Notably `flash_attn_dequant.glsl` already carries a comment about needing explicit `std430` +
`restrict` because these turbo blocks alias bindings at a different stride — so layout is already
known to be delicate here.

**Cheapest test:** bypass struct layout entirely in the turbo3 dequant — read from a flat
`uint8_t` buffer with explicit offsets (`ib*50 + 34 + j/8`) instead of `.signs[...]`. If Polaris
goes clean, it's confirmed as a layout issue. Alternatively dump `sizeof`/member offsets as the
shader sees them on GCN4 vs RDNA.

I have the RX 580 on a bench and am happy to run patches against it — it's a ~20 minute
turnaround per build, and the repro is deterministic so a fix will be unambiguous.

## Deltas from the original report (stating these for completeness)

| | @suhermanme | me |
|---|---|---|
| GPU | RX 580 Polaris | same class |
| backend | Vulkan/RADV | same |
| model | Qwen3.6-35B-A3B Q4_K_M (MoE) | Crow-9B Qwen3.5 IQ4_XS (dense) |
| context | 256,000 | 16,384 |
| offload | `--n-cpu-moe 36` | none |
| build | 9953 (`30d6881eb`) | 9971 (`c26cbdffc`) |

Those deltas cut in the useful direction: it reproduces with a **different model, 1/16th the
context, no CPU offload, and a build 18 commits newer** — so it's not depth-dependent, not
MoE-specific, and not already fixed.
