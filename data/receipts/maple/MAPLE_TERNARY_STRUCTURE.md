# Maple-Preview: the released BF16 checkpoint is already ternary

**Date:** 2026-08-05. **Status:** measured, single tensor, reproducible from public bytes.

## Claim

`deepgrove/maple-preview` ships **40.45 GB of BF16 safetensors**. Those weights are **not**
higher-precision master weights. Every expert row measured holds exactly three values —
`{-alpha_r, 0, +alpha_r}` — with a single per-row scale. The BF16 container is carrying
~1.58 bits of information per weight.

Consequence: `maple-f16.gguf` (40.46 GB) and the ternary body of `maple-tq2_0.gguf` (5.45 GB)
encode **identical information**. The f16 pack is a genuine dense reference, not a better model.

## Provenance (§10)

| field | value |
|---|---|
| repo | `deepgrove/maple-preview`, license MIT |
| revision | `ac1ddd79d2b5cb4406f5d2bebdf95406ce505a07` |
| repo lastModified | 2026-08-04T20:51:36Z |
| file | `model-00009-of-00009.safetensors` (0.43 GB, shard 9 of 9) |
| tensor | `model.layers.23.mlp.experts.100.down_proj.weight`, BF16, `[2048, 512]` |
| byte range fetched | data section starts at `8 + 24872 = 24880`; tensor at `data_offsets [0, 2097152]` |
| method | HTTP range request for the 2 MiB tensor only; no full-shard download |

Shard-9 safetensors header preserved alongside this file as `shard9_safetensors_header.json`
(202 tensors, 196 of them experts).

## Method

safetensors layout is `u64 LE header length` + JSON header + data. Read the header via range
request, resolve one tensor's absolute byte range, fetch only those bytes, reinterpret
`uint16 -> uint32 << 16 -> float32` (BF16 widening).

## Results

```
rows whose |values| are NOT a single scale: 0 / 2048
distinct row scales:                        95
level counts  -1: 316468 (30.2%)   0: 415884 (39.7%)   +1: 316224 (30.2%)
all row scales exactly representable in FP16: True
  scale range: 0.0262451 .. 0.285156
tensor-wide distinct values: 191   (95 magnitudes x +/- , plus zero)
```

**Positive verification (§1):** the discriminating statistic is `0 / 2048` rows deviating —
computed over every row, not sampled. `191` distinct values in a 1,048,576-element tensor is the
corroborating signal. `config.json` carries `"dtype": "bfloat16"` and `"quantize": true`; the flag
alone was *not* treated as evidence (§5 — measure the property, do not read the label).

## Why this matters: a near-zero-null kernel probe

TQ2_0 stores `q in {-1,0,+1}` at 2 bits plus one FP16 scale `d` per 256-element block. Maple's
scale is constant across an entire row, so every block in a row takes the same `d = alpha_r`.
The measured scales are **exactly representable in FP16** (range 0.026..0.285, comfortably normal;
BF16's 7 mantissa bits fit inside FP16's 10). The body therefore round-trips **losslessly**.

So for the ternary body, `KLD(maple-f16 || maple-tq2_0)` has a null of **exactly zero**, and any
observed divergence is *implementation* error — packing or kernel — never quantization loss.
That separation is normally unavailable: standard ladders conflate the two.

**Caveat that must be controlled (§2).** The tq2_0 pack is tiered — 168 ternary tensors, 2 Q4_0,
121 F32 — with **Q4_0 on embeddings and the output head** where the f16 pack has F16. That part
*is* lossy, so the raw f16-vs-tq2_0 comparison is not a clean null as shipped. A matched arm with
F16 embeddings/output head and a ternary body is required to isolate the kernel term.

## Limits

- **One tensor, one layer.** Layer 23 expert 100 `down_proj`. Attention and other layers not yet
  checked; the README's tiering implies attention is also ternary but that is unverified here.
- Says nothing about output quality, and nothing about whether the ternary structure arose from
  QAT or post-hoc collapse — only that the shipped weights *are* ternary.
- Level split is near-symmetric (30.2 / 39.7 / 30.2); no claim is made that this generalises.

## Downstream

The correct reference for a fidelity study of Maple is **not** "f16 vs tq2_0 = quantization
damage" — that framing measures nothing, because there is no precision to lose. See
`Protocol_Measurement_Standard.md` §5.
