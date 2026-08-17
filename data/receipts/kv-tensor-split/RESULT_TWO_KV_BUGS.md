# Two distinct KV bugs on `buun_vbr` / sm_60 — one silent, one loud, and the loud one blocks isolating the silent one

**2026-08-16.** `.73`, dual Tesla P100 (sm_60), 1063 MHz / 150 W.
Build **`buun_vbr` `a8e5b5a38`** ("ggml-backend-meta: allow sharded + full-width MIRRORED
binary ops"), 805 commits ahead of upstream `b9637`.
Model `unsloth-Qwen3.8-27B-Q6_K.gguf` — **`head_dim` 256**, 24 attn heads / 4 KV heads
(**GQA 6:1**). `temperature 1.0 / top_p 0.95 / top_k 20`, `cache_prompt:false`.

## The map

| K | V | split | result |
|---|---|---|---|
| f16 | f16 | tensor | **clean** (8/8, both ctx 16384 and 40960) |
| `q8_0` | `q8_0` | tensor | **silent degeneration** 8/8 |
| `q8_0` | `q8_0` | tensor, ctx 40960 | **silent degeneration** 8/8 |
| `q8_0` | `q8_0` | **layer** | **silent degeneration** 3/3 |
| `q8_0` | `q8_0` | tensor, **no MTP** | **silent degeneration** 3/3 |
| `q8_0` | **turbo4** | tensor + MTP | **clean** 3/3 |
| `q8_0` | **f16** | tensor | **HARD ABORT** |
| **f16** | `q8_0` | tensor | **HARD ABORT** |

## Bug A — `q8_0` K+V silently collapses

Every response is `len=N maxrun=N uniq=1`: the **entire generation is one repeated
character**, on the **first request**, deterministically. Not degraded quality — total
collapse.

**Independent of everything tested:** split mode (`tensor` and `layer` both fail),
speculation (fails with and without `--spec-type draft-mtp`), and context size (16384 and
40960 identical). 22 degenerate responses, zero exceptions.

## Bug B — f16 mixed with any quantized KV aborts under tensor split

```
W internal AllReduce init failed (n_devices != 2?); falling back to meta-backend butterfly
ggml/src/ggml-backend-meta.cpp:533: GGML_ASSERT(ret.axis != GGML_BACKEND_SPLIT_AXIS_UNKNOWN) failed
```

Fires for **`q8_0` K + f16 V** and **f16 K + `q8_0` V** alike. Both-quantized pairs are fine
(`q8_0`+turbo4 clean), and both-f16 is fine. So the split-axis logic appears unable to resolve
a **type-class mismatch** — a plain type paired with a blocked/quantized one — rather than
having trouble with any particular codec.

The assert is in **`ggml-backend-meta.cpp`, the file this build's HEAD commit modifies.**

**The AllReduce warning is a red herring.** It appears on *clean* tensor-split runs too —
P5 (clean) logged 2 of them and 0 asserts; P4 (degenerate) logged 1 and 0 asserts. The
butterfly fallback is normal here; only the mixed-type case asserts.

## The full codec sweep — stock collapses, buun's works

| K | V | class | result |
|---|---|---|---|
| f16 | f16 | plain | **clean** |
| `q8_0` | `q8_0` | **stock** | **collapse** (22 responses, 0 exceptions) |
| `q4_0` | `q4_0` | **stock** | **collapse** 3/3 |
| `q8_0` | turbo4 | mixed | **clean** 3/3 (with MTP) |
| `q8_0` | turbo4 | mixed | **clean** 3/3 (without MTP) |
| turbo8 | turbo4 | buun | **clean** 3/3 |
| turbo3_tcq | turbo3_tcq | buun | **clean** |
| vbr | vbr | buun | clean — **but `kv_bpv: 16.0`, never left entry tier**, so this is f16 in disguise and says nothing about the codec |

**Two independent stock codecs collapse; every buun codec that actually engages passes.**
That is much stronger than a single-codec quirk, and it matches the source: `fattn.cu:2268-2284`
enumerates D=256 type pairs and lists **only turbo types plus f16 pairings** — no stock
quantized types appear. The fused path is additionally gated on
`turing_mma_available() || amd_wmma_available()`, **neither true on sm_60**.

## Bug B blocks the clean isolation of Bug A

The natural control for "is it K or V?" is to hold one side at f16 and quantize the other.
**Both of those configurations abort**, so that experiment cannot be run on this build.

What survives is a single-variable inference from the arms that do run: with **K held constant
at `q8_0`**, changing V from `q8_0` to `turbo4` flips the outcome from collapse to clean.
**V is implicated in Bug A.** But `q8_0` V *alone* is not independently testable here.

## Working configurations

- `-ctk f16 -ctv f16` — clean, any split, any context tested
- **`-ctk q8_0 -ctv turbo4`** — clean with **`-sm tensor` + MTP**, i.e. the full 1.62x split
  speedup *and* a quantized K cache. This is the "speed and correctness" answer.

## Predictions, scored

| # | prediction | conf | outcome |
|---|---|---|---|
| V1 | P2 (f16 K + `q8_0` V) degenerates | 0.75 | **WRONG** — it aborts, different failure mode |
| V2 | P1 (`q8_0` K + f16 V) is clean | 0.70 | **WRONG** — it aborts too |
| V3 | P5 (`q8_0` K + turbo4 V) is clean | 0.80 | **CORRECT** |
| V4 | P9 (`q4_0` K+V) — genuinely unsure which way | 0.50 | **collapsed** — so Bug A is not `q8_0`-specific |

Three earlier mechanism hypotheses also died: block/head misalignment (geometry is clean —
4 KV heads split 2/2, `head_dim` 256 gives 8 whole `q8_0` blocks per head), tensor-split
sharding (P3 fails under `-sm layer`), and MTP (P4 fails without it).

## Not established

- **Whether this is `head_dim` 256-specific.** buun's fused attention has an explicit D=256
  type-pair dispatch table (`fattn.cu:2268-2284`) listing **only turbo types — `q8_0` is
  absent** — and the fused path is gated on `turing_mma_available() || amd_wmma_available()`,
  **neither of which is true on sm_60**. Suggestive, not proven. A D=128 model on this build is
  the decisive test and `.73` currently holds only D=256 models.
- **Whether either is a regression.** `.194` carries a different `buun_vbr` commit
  (`1abf2d28c`) and is the natural second data point, but is occupied by a long ladder.
- **Whether Tom's fork reproduces.** Note his fork has `TURBO_AUTO_ASYMMETRIC`
  (`llama-kv-cache.cpp:153`) which **silently upgrades K to `q8_0` at GQA >= 6** — and this
  model is exactly 6:1 — so any turboquant KV test must set `TURBO_AUTO_ASYMMETRIC=0` or it is
  measuring a different configuration than it asked for.
