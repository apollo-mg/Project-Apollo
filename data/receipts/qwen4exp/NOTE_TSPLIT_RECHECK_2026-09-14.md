# Note — `-sm tensor` on qwen4exp is fixed, and layer is still the faster choice on 4× P100

**Run 2026-09-14 09:01–09:07 on `.194`** (4× P100, sm_60, 150 W / 1063 MHz), buun **`c7f114d34`**,
`GGML_CUDA_ALLREDUCE=internal` pinned. Prompted by buun asking whether tensor or layer ended up faster on
the P100s. **Run specifically to check a claim before it was sent to him** — the draft answer cited an
08-28 finding without its architecture scope and without rechecking the build.

## 1. The ≥3-device corruption does not affect dense models

Dense Qwen3.8-27B UD-IQ3_XXS (11.9 GB — fits at every device count with no spill, so device count is the
only variable):

| arm | VRAM per card | probes |
|---|---|---|
| `-sm layer` ×4 (reference) | 3169/3009/3169/3527 | 391 · Paris · 1–10 |
| `-sm tensor` ×2 | 5935/5935 | 391 · Paris · 1–10 |
| `-sm tensor` ×3 | 4089/4091/4105 | 391 · Paris · 1–10 |
| `-sm tensor` ×4 | 3175/3175/3175/3175 | 391 · Paris · 1–10 |

**Clean at every count.** Even VRAM confirms real tensor parallelism rather than a silent fallback.

## 2. qwen4exp tensor split is FIXED between `c232282aa` and `c7f114d34`

Flash-Next UD-Q2_K_XL, `-ngl 99`, fully resident on four cards:

| `-sm` | decode | VRAM per card (total) | greedy output |
|---|---|---|---|
| **layer** | **17.59 tok/s** | 13431/12403/12403/11771 (**50,008 MiB**) | coherent |
| tensor | 12.30 tok/s | 13213 × 4 (**52,852 MiB**) | coherent |

**On `c232282aa` (2026-08-28) this exact configuration emitted `////////////////` at 6.14 tok/s with no
assert** (`RESULT_c232282aa_VERIFY.md` §6). It is now correct: **the two arms produced byte-identical greedy
text** on all three probes, including a 128-token continuation. At temperature 0 that is the strong form of
the check — not "coherent", but "the same computation".

**So the 08-28 result was real, was qwen4exp-specific, and is now stale.** It must not be repeated as a
current multi-P100 tensor-split bug.

## 3. The answer to buun's question: layer, for this model

**Layer is 1.43× faster on Flash-Next** (17.59 vs 12.30) and uses 2.8 GB less VRAM.

The dense 27B goes the other way — `-sm tensor` is **1.6–1.7×** layer there (Q6_K 13.22 vs 7.81; EXL3
4.00bpw 11.26 vs 6.96, both on `.73`'s two P100s), because **two-card layer split benched bit-identical to a
single card** (`qwen38-splitmode/RESULT_P100_SM_TENSOR.md`).

**Interpretation, not measurement:** tensor split wins where layer split leaves cards idle, and loses where
decode is already overhead-bound and the PCIe all-reduce costs more than the parallelism saves. Flash-Next
decode was independently found overhead-bound in Stage 3. Untested.

## Limits

- **One prompt shape, one rep per arm.** These are coherence checks with a timing attached, not a
  benchmark. The decode figures are short chat requests and are **not** comparable to Stage 1/3/4's
  `/completion` numbers at 500/1800/3600-token prompts (F-Q2 measured 21.05 tok/s there).
- Flash-Next was tested at **4 devices only** — Q2_K_XL needs ~50 GB, so 2 and 3 cards cannot hold it
  without spill, which would confound device count with placement.
- `.194` defaults to NCCL for `-sm tensor` and NCCL fails on its P100s; `GGML_CUDA_ALLREDUCE=internal` was
  pinned throughout ([[allreduce-internal-inert-on-pascal]]).

Artifacts: `tsplit/` — `check.log`, `fn.log`, and the two scripts.
