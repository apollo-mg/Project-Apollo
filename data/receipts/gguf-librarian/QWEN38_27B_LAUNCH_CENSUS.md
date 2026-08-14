# Qwen 3.8 27B, unsloth GGUFs — launch-day census

**Date:** 2026-08-14, within the hour of `unsloth/Qwen3.8-27B-GGUF` appearing.
**Method:** HTTP range requests over the GGUF tensor table (`gguf_remote_dump.py`).
~4 MiB per file, no weights downloaded. Total cost of everything below: about a minute.

## It is DENSE, not MoE

| field | value |
|---|---|
| `general.architecture` | **`qwen35`** (not `qwen35moe`) |
| `block_count` | 65 |
| tensors | 866 |
| **expert tensors** | **0** |

**A pre-registered prediction was wrong, and wrong in its premise.** Before the drop this
campaign predicted (0.6) that the 27B would carry a 2048-wide expert FFN like
Qwen3.8-2.4T-A95B, clearing the 1024 KiB pre-Ampere floor and letting Pascal engage the MoE
cache stock. That question does not exist: there are no experts. The correct first move was
to check *whether* it has experts before predicting *their shape*. Recorded because
predicting the shape of a thing that is absent is a more instructive error than a bad
number.

Consequences: the MoE expert cache is irrelevant to this model on every backend, and the
`GGML_CUDA_MOE_CACHE_MIN_EXPERT_KB` / `MIN_CC` overrides that make Pascal work on
`qwen35moe` models have nothing to act on here.

## No quant in this ladder is uniform

Six quants, tensor-type census from the header:

| file | actual tensor mix (count by ggml type) |
|---|---|
| `Q4_K_M` | Q4_K 294, **Q6_K 67**, Q5_K 48, Q8_0 1 |
| `UD-Q4_K_XL` | **Q5_K 325**, Q4_K 97, IQ4_XS 65, Q6_K 19 |
| `IQ4_XS` | IQ4_XS 288, **Q5_K 113**, Q4_K 7, Q6_K 1, Q8_0 1 |
| `UD-IQ2_M` | IQ3_XXS 224, IQ3_S 99, **IQ1_M 96**, IQ2_S 64, IQ4_XS 21, Q3_K 1, Q2_K 1 |
| `UD-Q8_K_XL` | Q8_0 453, **BF16 53** |
| `Q6_K` | Q6_K 361, **Q8_0 49** |

(`F32` counts omitted — norms and biases, present in all of them.)

### Three that change how a benchmark should be read

**1. `UD-Q4_K_XL` holds more `Q5_K` tensors than `Q4_K`** — 325 against 97. Reading that
filename as "a Q4 quant" is wrong by tensor count; it is majority Q5. Anyone comparing it
against a stock `Q4_K_M` is not comparing two Q4 recipes.

**2. `UD-IQ2_M` contains 96 `IQ1_M` tensors** — a full tier below the label, and `IQ1_M` is
where quality degrades hardest. If a disappointing IQ2 number gets posted today, this is
the first thing to check before attributing it to the model.

**3. `UD-Q8_K_XL` is 53 `BF16` tensors on top of 453 `Q8_0`.** It is not a pure Q8
reference point, and BF16 is poorly served on Pascal — relevant to any P100 arm using it as
the high-precision anchor.

## Fleet fit

Dense at 27B, so placement is simple — no `-ncmoe`, no cache-aware fit, none of the
MoE machinery this campaign has spent a week characterising:

| quant | size | fits |
|---|---|---|
| `Q6_K` | 21.31 GiB | 2x P100 (32 GB) comfortably |
| `Q5_K_M` | 18.47 GiB | 2x P100 |
| `UD-Q4_K_XL` | 16.69 GiB | 9070 XT (16 GB) with light offload |
| `UD-IQ3_XXS` | 11.10 GiB | 9070 XT fully resident |

## Limits

- Header-only. **Nothing was run**; no quality or throughput claim is made here.
- Tensor *counts* are not parameter-weighted: 96 `IQ1_M` tensors out of ~866 is a statement
  about how many tensors, not what fraction of the weights. Sizing that properly needs the
  per-tensor dimensions, which the same header carries and which this pass did not total.
- Only 6 of 23 weight files were censused. The rest are cheap to add.
