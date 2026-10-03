# Note -- Naive-N0.5-Flash descends from MiMo-V2.5 (the post-trained release), not MiMo-V2.5-Base, and moved about 0.5-0.8x as far from it as Xiaomi's own post-training moved Base: real training, not a light fine-tune, but not a new model either.

**2026-10-03**, Mark asked for a "brief weight drift check" after reading the card of `NaiveAI/Naive-N0.5-Flash`
(@ `0235b3b5`, created 09-27, 309B MoE / 15.5B active, MIT).
- **The card's claims:** "builds on the open-weight MiMo-V2.5 base model", global attention replaced by DeepSeek
  Sparse Attention (GQA4), then "3.25T tokens of multi-stage training".
- **Missing:** the HF `base_model` field, and the repo has no safetensors index.

**Method:** `tools/hf_tensor_drift.py` (new).
- **Reading:** HTTP range reads of the first 256 rows of each tensor (or all of a 1-D tensor). No download, a few MB
  per tensor.
- **Naive's shard map:** built from its 49 shard headers.
- **MiMo:** e4m3 FP8 with 128x128 block scales, dequantized.
- **Metric:** relative L2 = ||a - b|| / ||a||.
- **Yardstick:** MiMo-V2.5-Base vs MiMo-V2.5, i.e. Xiaomi's own post-training distance on the same tensors.

| tensor | Naive vs Base | **Naive vs V2.5** | Base vs V2.5 |
|---|---:|---:|---:|
| router (F32), layer 10 | 0.083 | **0.048** | 0.074 |
| router (F32), layer 30 | 0.151 | **0.112** | 0.112 |
| token embedding, 256 rows | 0.183 | **0.118** | 0.158 |
| expert L10 #0 gate_proj | 0.122 | **0.060** | 0.105 |
| expert L30 #100 up_proj | 0.163 | **0.102** | 0.129 |
| expert L20 #17 down_proj | 0.147 | **0.066** | 0.127 |
| o_proj, SWA layer 10 | 0.163 | **0.096** | 0.139 |
| o_proj, layer 5 (global -> DSA) | 0.220 | **0.131** | 0.182 |
| layer norms (3) / final norm | 0.002-0.007 | 0.001-0.006 | 0.002-0.007 |

## What it shows

- **The parent is MiMo-V2.5, the post-trained release.** All 11 tensors are closer to it than to MiMo-V2.5-Base.
  - The distances fit "V2.5 plus its own drift": e.g. router L30, sqrt(0.112^2 + 0.112^2) = 0.158 predicted against
    0.151 measured.
  - The card's "MiMo-V2.5 base model" reads as "built on MiMo-V2.5", not on the -Base checkpoint.
- **The drift is substantial.** Experts moved 0.06-0.10 from V2.5, which is 0.5-0.8x Xiaomi's own Base-to-instruct
  distance (0.105-0.13).
  - A LoRA or a short fine-tune would sit near the FP8 floor (~0.02-0.03 against a dequantized copy).
  - This is consistent with large-scale continued training. Weight drift cannot confirm a token count (3.25T): the
    learning-rate schedule matters as much.
- **The layer converted to DSA moved most** (o_proj 0.131 against 0.096 in a sliding-window layer), as expected
  from the architecture change.

## Limits

- 11 tensors, 256 rows each: a sample, not the model.
- MiMo's published weights are FP8. Their dequantization noise (~0.02-0.03) is inside every MiMo comparison.
- Whether the NaiveAI benchmarks hold is a separate question: their charts omit MiMo-V2.5 itself, the one baseline
  this lineage makes necessary.
