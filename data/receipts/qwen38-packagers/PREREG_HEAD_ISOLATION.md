# PREREG — does draft-head precision matter? Identical body, only `blk.64` varies

**Sealed 2026-08-15, before any variant was built.** Node: desktop RX 9070 XT (RDNA4,
gfx1201, 16 GiB), `moe-cache-test` HIP build, `-ngl 999 -c 8192 -fa on -np 1`, temp 0 /
top_k 1 / seed 1234, `--spec-draft-n-max 3`.

## Why this exists: the packager A/B cannot answer the question

`RESULT_MTP_HEAD_QUANT.md` found bartowski shipping a `Q4_0` MTP head where unsloth ships
`Q6_K`. The A/B running on `.73` compares those two files — but **they differ in the body
too** (bartowski `Q8_0` x120 against unsloth's x48, which is why his file is 0.54 GiB
larger). Any difference it finds is unattributable between head and body. That test answers
"what do you get downloading from A vs B", which is worth knowing and is not this question.

Here the files are built rather than downloaded: one bf16 source, one imatrix, one ftype,
and a `--tensor-type` override on `blk.64` alone.

| variant | `blk.64` weights | everything else |
|---|---|---|
| `headF16` | `F16` | IQ3_XXS body, imatrix, identical |
| `headQ4_0` | `Q4_0` — bartowski's choice | ditto |
| `headIQ4_XS` | `IQ4_XS` — unsloth's dominant choice | ditto |
| `headQ6_K` | `Q6_K` | ditto |

Build order is `F16`, `Q4_0`, `IQ4_XS`, `Q6_K` on purpose: the first two are the
maximum-contrast pair, so a partial run still answers the question. If `F16` and `Q4_0` are
indistinguishable, draft-head precision does not matter and the middle rungs are not worth
the compute.

## Verified before spending the compute

- `llama-quant.cpp:185` — `--tensor-type` options are **regex** patterns, so `blk\.64\.`
  is a valid selector.
- `llama-quant.cpp:294` — tensors with `< 2` dims are never quantised, so the **F32 norms
  inside `blk.64` survive the override untouched**.
- `llama-quant.cpp:299` — only names ending in `weight` are quantised.

Together: the override hits exactly the 8 weight tensors that constitute the MTP head.

## Stage 2 tests a claim the earlier receipt only inferred

`RESULT_MTP_HEAD_QUANT.md` argued from source that an `IQ3_XXS` target on `blk.64` **must**
abort, because bartowski's imatrix contains no entry for that block and `IQ3_XXS` is on the
`tensor_requires_imatrix` list. That was a source-reading inference. Stage 2 runs the
quantise with no override and records what actually happens.

| # | prediction | conf |
|---|---|---|
| H0 | Quantising `IQ3_XXS` with no `blk.64` override **aborts**, naming a `blk.64` tensor | 0.80 |

## Predictions, sealed

| # | prediction | conf |
|---|---|---|
| H1 | Draft acceptance is monotonically non-decreasing in head precision (`Q4_0` <= `IQ4_XS` <= `Q6_K` <= `F16`) | 0.60 |
| H2 | The `F16` head beats the `Q4_0` head on acceptance by >= 2 pp | 0.55 |
| H3 | **Control:** MTP-off throughput is within 1 % across all four variants | 0.90 |
| H4 | **Control:** the files are byte-identical outside `blk.64` | 0.85 |
| H5 | The relative spread in acceptance exceeds the relative spread in t/s | 0.65 |
| H6 | Even the `Q4_0` head is net-positive for MTP (> 1.0x) | 0.85 |

H3 and H4 are the ones that decide whether anything else can be read. The whole design rests
on the bodies being identical; if MTP-off throughput moves between variants, something other
than the head changed and every other number is confounded.

H2 at 0.55 is the honest position. `Q4_0` is 4.5 bpw against `IQ4_XS` at 4.25 — nominally
*more* bits — but `IQ4_XS` uses a non-linear codebook, so the ordering by bit width and the
ordering by quality are not the same ordering. That is exactly why the `F16` ceiling is in
the design.

## Limits stated in advance

- **bartowski's published imatrix is used as-is** and credited. It is his calibration data,
  not a neutral one, and it covers `blk.0-63` only — which is the point.
- One base model, one body ftype, one draft depth, one architecture (RDNA4). A `Q4_0` head
  might cost more or less on Pascal, where the kernels differ.
- Throughput and acceptance only. **No quality measurement of the output text.** A worse
  draft head costs speed, not correctness — speculative decoding is exact by construction,
  since rejected drafts are discarded. Nothing here measures whether the *model* got worse,
  because it cannot have.
- `-np 1`. Batching changes the economics of speculation substantially.
