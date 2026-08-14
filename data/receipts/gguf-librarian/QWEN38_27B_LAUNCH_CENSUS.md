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

## Vision is a separate module, and the two mmproj builds are not equivalent

The text GGUF carries **zero** vision tensors and no multimodal KV keys — vision ships as
the standard llama.cpp `--mmproj` sidecar, same arrangement as Qwen 3.6.

Both mmproj files are **honestly labelled** (unlike the text ladder): F16 is F16+F32, BF16
is BF16+F32. Same architecture in both — `qwen3vl_merger`, 27 vision blocks, 1152-dim,
768 px image / 16 px patch, `has_vision_encoder=True`, **no audio encoder**.

| | `mmproj-F16` | `mmproj-BF16` |
|---|---|---|
| tensors | 334 | 334 |
| F32 | 222 | **224** |
| low-precision | F16 112 | BF16 110 |
| projector / patch-embed | F32 3, **F16 4** | **F32 5**, BF16 2 |

The BF16 build keeps **two more projector tensors at F32**. Plausibly deliberate: BF16 has
F32's exponent range but only 8 mantissa bits against F16's 10, and the projector is where
vision embeddings enter the text model's space, so its error propagates into every
downstream token. Not verified with the packager — the tensor counts are measured, the
motive is inference.

Consequence: **use `mmproj-F16` on Pascal** (sm_60 has no native BF16; it would be emulated
or upconverted). Either works on RDNA4. And a vision-quality comparison between these two
files is **not** a clean F16-vs-BF16 test — it compares two different mixed recipes, the
same trap as the text ladder at smaller scale.

Cost note: mmproj is a flat ~0.87 GiB on top of any text quant — it is not quantised with
the ladder. On a 16 GB card that is roughly one quant tier of headroom.

## Every quant ships an MTP draft head — and the build discards it

`llama-server` at `bb3c3fa` (giveen/moe-cache) loading `UD-IQ2_M` prints **15 discard
warnings**, all for `blk.64.*`:

```
W model has unused tensor blk.64.nextn.eh_proj.weight (size = 27852800 bytes) -- ignoring
W model has unused tensor blk.64.nextn.enorm.weight  -- ignoring
W model has unused tensor blk.64.nextn.hnorm.weight  -- ignoring
W model has unused tensor blk.64.nextn.shared_head_norm.weight -- ignoring
   ... plus blk.64 attn_{q,k,v,output,norm,q_norm,k_norm} and ffn_{gate,up,down}
```

Verified over range requests that this is **not** a packaging accident and **not** specific
to one quant:

| file | `block_count` | `blk.64.*` tensors | `nextn` tensors | KV |
|---|---|---|---|---|
| `UD-IQ2_M` | 65 | 15 | 4 | `qwen35.nextn_predict_layers = 1` |
| `Q4_K_M` | 65 | 15 | 4 | `qwen35.nextn_predict_layers = 1` |
| `UD-Q8_K_XL` | 65 | 15 | 4 | `qwen35.nextn_predict_layers = 1` |

The whole ladder carries a complete self-speculation draft layer — a full transformer block
(attention + FFN) plus the `nextn` projection and norms — as block 64 of 65.

**Why this matters here.** `data/receipts/mtp-sm60/SUMMARY.md` measured **1.70x throughput**
from MTP on 2x P100, on a model with the *same* `nextn_predict_layers = 1`, via
`--spec-type draft-mtp --spec-draft-n-max 2`. That is a free ~1.7x on interactive serving
that this build is currently throwing away at load time.

Two caveats carried forward from that receipt, unchanged:

- MTP is **not bit-exact** — 4 of 5 prompts diverged at temp 0 against a clean 5/5
  determinism control. It is a serving win, never something to enable on one arm of an A/B.
- Enabling it on one arm by accident is a documented hazard: the original stage-2 queue did
  exactly that, pointing ThinkingCap at an MTP GGUF and stock at a non-MTP one.

**Not yet tested:** whether `--spec-type draft-mtp` actually engages on `qwen35` arch in
this build, or whether — like the Vulkan MoE cache — the tensors load but no code path
consumes them. The discard warnings say this particular server binary does not wire them
up; a build that does is a separate question. Engagement gets proven from the log before
any speedup is claimed.

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
