# Validity check — the quantized KV arms really were quantized

**2026-08-17**, `.73`, dual P100. Binary **TheTom `f6124e9`**. Raw `~/xfork_vram/`, log
`~/kv_vram.log`, script `kv_vram.sh`.

## Why this had to be checked

`RESULT_D128.md` concludes the collapse is D=256-only **because `q8_0` and `q4_0` arms came
back clean at D=128**. `RESULT_XFORK.md` concludes the collapse needs K *and* V quantized
**because single-sided arms came back clean**. Both conclusions are drawn from *clean*
results on *quantized* arms — and a silent fallback to f16 at an unsupported
(type, head-dim) pair produces exactly that, while measuring nothing.

This is not a hypothetical failure mode here. `INDEX.md` C2 records a whole VBR campaign
invalidated this way: `/slots` read `kv_bpv: 16.0` throughout, and "VBR is sharper" turned
out to mean "VBR is f16".

`/slots` on this build exposes no `kv_bpv`, so the check is VRAM: same model, same context,
only `-ctk`/`-ctv` differ, so the delta is the cache.

## D=128 (Llama-3.2-3B-Instruct-BF16) — the arms `RESULT_D128.md` rests on

| arm | K | V | total VRAM | Δ vs f16 |
|---|---|---|---|---|
| A1 | f16 | f16 | 9390 MiB | — |
| A2 | `q8_0` | `q8_0` | 8650 MiB | **−740** |
| A3 | `q4_0` | `q4_0` | 8202 MiB | **−1188** |

Monotonic and in the right order. `q8_0` is 1.0625 bytes/value against f16's 2 (ratio
0.531); `q4_0` is 0.5625 (ratio 0.281). **Quantization engaged.**

## D=256 (Qwen3.8-27B-Q6_K) — the "either side alone" arms

| config | total VRAM | Δ |
|---|---|---|
| `-c 16384` f16 + f16 | 26250 MiB | — |
| `-c 16384` `q8_0` + f16 | 26010 MiB | **−240** |
| `-c 16384` f16 + `q8_0` | 26010 MiB | **−240** |
| `-c 16384` `q8_0` + `q8_0` | 25770 MiB | **−480** |
| `-c 4096` f16 + f16 | 25434 MiB | −816 |

**Exactly half the saving for one side as for both, symmetric in K and V.** That is the
signature of two equal halves, one of which changed type.

## The 240 MiB looked wrong, and the error was mine

Predicted saving was ~960 MiB per side, from 64 layers x 4 KV heads x 256 dim x 2 x 2 bytes
= 256 KiB/token = 4096 MiB at 16384. Measured was a quarter of that, which is exactly the
shape a partial fallback would have.

The `-c 4096` arm settles it. Dropping 12288 tokens of context freed 816 MiB, so the cache is
**68 KiB/token**, and f16 KV at 16384 is **~1088 MiB — not 4096 MiB**. Against that true
baseline:

| | predicted | measured |
|---|---|---|
| both sides `q8_0` | 510 MiB saved | **480** |
| one side `q8_0` | 255 MiB saved | **240** |

Within 6% on both. **The arms are valid; the naive KV formula was wrong.**

## Consequence: a number in `CLAUDE.md` is 3.8x too high

`CLAUDE.md` states Qwen3.8-27B uses "~256 KB KV/token". Measured is **~68 KiB/token**.

Working backwards, `68 KiB / (2 x 4 heads x 256 dim x 2 bytes)` implies roughly **17 of 64
layers** hold a full-context KV cache, consistent with a hybrid attention pattern — about one
full-attention layer in four, the rest local/sliding-window with a small cache.

This matters beyond bookkeeping: it means a 16 GB card fits roughly **4x more context** on
this model than the folklore number predicts, and every context-budget estimate made from
256 KiB/token has been badly pessimistic.

**Not fully established:** the 17-layer inference is arithmetic from a VRAM delta, not a read
of the architecture. The measurement (68 KiB/token) is solid; the *explanation* (hybrid
attention) is inferred and should be confirmed against the config before being quoted as
fact — `AFM-17` applies, in the opposite direction from usual.

## Method note

VRAM deltas are a blunt instrument — they include compute buffers, CUDA context, and the MTP
draft cache. What makes them usable here is that **only `-ctk`/`-ctv` change between arms**,
so everything else cancels, and the context-scaling arm provides an independent estimate of
the ctx-dependent term. Two independent routes agreeing to 6% is what licenses the
conclusion, not either number alone.
