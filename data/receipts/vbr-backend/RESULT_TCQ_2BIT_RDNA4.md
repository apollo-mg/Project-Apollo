# On gfx1201, ANY turbo KV codec collapses generation on GQA ≥ 6 models

**2026-08-19.** Control plane **RX 9070 XT (gfx1201, ROCm/HIP)** and **`.194` Tesla P100
(sm_60, CUDA)**. Binary **buun `02f8581c65`** on both — same fork, same commit, only the
device differs. Script `vbr_backend.py`; raw logs in `raw/`; every prediction pre-registered
in `PREDICTION_STATIC_TIERS.md` and scored there, including four falsifications.

> **This receipt was rewritten three times.** It claimed "2-bit weights", then "low-bit
> weights", then "symmetric TCQ". All three were wrong. A 2-bit 9B runs clean; a 3-bit 27B
> collapses; `turbo4` is not a TCQ codec and collapses; and asymmetric pairs collapse too.
> The weight ladder was a confound — every rung was the same base model — and the TCQ framing
> survived only because no non-TCQ turbo had been run.

## The whole KV matrix on the collapsing model

`Qwen3.8-27B-AD-IQ2_S`, GQA 6:1, gfx1201, ctx 4096. **Eight of eight turbo configurations
collapse; three of three stock configurations are clean.**

| K | V | any turbo? | result |
|---|---|---|---|
| f16 | f16 | no | **clean 10/10** |
| `q8_0` | `q8_0` | no | **clean 9/10** |
| `q4_0` | `q4_0` | no | **clean 9/10** |
| `turbo8` | `turbo8` | yes | COLLAPSE |
| `turbo4` | `turbo4` | yes | COLLAPSE |
| `turbo3_tcq` | `turbo3_tcq` | yes | COLLAPSE |
| `turbo1_tcq` | `turbo1_tcq` | yes | COLLAPSE |
| `turbo8` | `turbo4` | yes | COLLAPSE |
| `turbo4` | `turbo3_tcq` | yes | COLLAPSE |
| `q8_0` | `turbo8` | yes | COLLAPSE |
| `q8_0` | `turbo4` | yes | COLLAPSE |
| `q8_0` | `turbo3_tcq` | yes | COLLAPSE |

**One turbo tensor anywhere in the cache is sufficient.** Bit depth is irrelevant — `turbo8`
at 8.125 bpv fails identically to `turbo1_tcq` at 1.25. TCQ vs classic is irrelevant. Which
side carries it is irrelevant. `q8_0` K + `turbo4` V is **poshih's exact configuration in
`turboquant#311`**, reproducing here on different hardware and a different fork.

**Consequence: on gfx1201 the turboquant KV cache is unusable for GQA ≥ 6 models** — not
degraded, degenerate from the first request and permanently. `Qwen3.5-9B` at GQA 4:1 runs the
same codecs clean at 32k, so this is scoped to the model class, not the card.

### Why VBR always lands there

The degrade ladder is per-layer and per-side (`llama-vbr-degrade-orders.inc`, generated
2026-07-05). The `q27` order — Qwen3.6-27B, hybrid, 16/64 KV layers, our exact model class —
runs 160 steps. Its **first step is already a turbo tier**, so any budget pressure at all puts
turbo tensors in the cache; by step 64 layer 3 holds TCQ on both sides, and all 16 of 16 KV
layers end there. `VBR_DEGRADE_ORDER=<file>` overrides the table at runtime
(`llama-kv-cache.cpp:3756`), but no ordering helps when every turbo tier is unsafe — only the
f16 entry tier is.

## The result

Collapse = every response is pure `!` to the token cap, HTTP 200, `finish_reason: length`,
server never recovers. Clean = normal answers, `finish_reason: stop`, canary alive after.

### RX 9070 XT — gfx1201 — `turbo3_tcq` symmetric

| model | base | quant scheme | heads/kv | **GQA** | D | `turbo3_tcq` | f16 |
|---|---|---|---|---|---|---|---|
| Llama-3.2-3B | Llama 3.2 | BF16 | 24/8 | **3:1** | 128 | clean 9/10 | clean 9/10 |
| Qwen3.5-9B | Qwen 3.5 | Q8_0 | 16/4 | **4:1** | 256 | clean 10/10 | clean 10/10 |
| Qwen3.5-9B | Qwen 3.5 | UD-Q2_K_XL | 16/4 | **4:1** | 256 | clean 10/10 | clean 10/10 |
| Qwen3.8-27B | Qwen 3.8 | AD-IQ2_XS | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 9/10 |
| Qwen3.8-27B | Qwen 3.8 | AD-IQ2_S | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 9/10 |
| Qwen3.8-27B | Qwen 3.8 | UD-IQ2_M | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 10/10 |
| Qwen3.8-27B | Qwen 3.8 | UD-Q2_K_XL | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 10/10 |
| Qwen3.8-27B | Qwen 3.8 | AD-IQ3_XXS | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 9/10 |
| Ternary-Bonsai-27B | Qwen 3.6 | ternary Q2_g64 | 24/4 | **6:1** | 256 | **COLLAPSE** | clean 10/10 |

`turbo1_tcq` (1.25 bpv) behaves the same way: clean at GQA 4:1, collapse at 6:1, and at
GQA 3:1 it degrades to coherent *wrong* answers rather than `!` spam.

### Tesla P100 — sm_60 — everything clean

| model | weights | D | f16 | `q8_0` | `turbo3_tcq` |
|---|---|---|---|---|---|
| Llama-3.2-3B | BF16 | 128 | 9/10 | 9/10 | 9/10 |
| Llama-3.2-3B @ 64k ctx | BF16 | 128 | 9/10 | 9/10 | 9/10 |
| Qwen3.8-27B | UD-IQ2_M | 256 | 10/10 | 10/10 | **9/10** |
| Qwen3.8-27B | Q6_K, 2 GPU, `-sm layer` | 256 | 10/10 | 10/10 | — |

**The decisive pair:** `Qwen3.8-27B-UD-IQ2_M.gguf`, **md5 `7ba3d070fecfd7f1324b9e08887f5b8c`
verified identical on both machines**, same binary commit, same ten items — **clean 9/10 on
the P100, COLLAPSE at item 1 on gfx1201.**

## What was ruled out, and by what

- **Weight precision.** A 2-bit 9B is clean; a 3-bit 27B collapses. Five quants of the 27B
  spanning 2- and 3-bit all collapse, and an 8-bit 9B is clean. Precision does not predict.
- **Quant family.** I-quants, K-quants and a **ternary** quant all collapse at GQA 6:1.
- **Packager and checkpoint.** AtomicChat and unsloth recipes collapse; two different base
  models (Qwen 3.8 and a Qwen 3.6 derivative) collapse.
- **Head dim.** D=256 is clean at GQA 4:1 on the same device.
- **Context depth.** 3B at 65,536 ctx — 4× allocation — clean. 27B collapses at ctx 4096.
- **Quantized KV generally.** Stock `q8_0` **and** `q4_0` are clean on a 27B that TCQ kills.
- **The VBR dynamic controller.** `vbr` is the CLI alias for `turbo3_tcq`; the static codec
  fails identically.
- **The `turbo1_tcq` floor tier.** The nominal 3.25 bpv tier fails the same way.
- **The auto-asymmetric gate.** `TURBO_AUTO_ASYMMETRIC` does not exist in buun's fork (it is
  TheTom's, `src/llama-kv-cache.cpp:136`), and the measured allocation delta between
  `turbo1_tcq` and `turbo3_tcq` on the 27B was **131 MiB against 128 predicted for a
  symmetric change and 64 for a K-pinned one** — so K was never silently rewritten.

**What predicts the outcome is GQA ≥ 6, on gfx1201, with a TCQ codec on both sides.**

## Validity

Every arm records measured VRAM allocation (sysfs on amdgpu, `nvidia-smi` on CUDA), because a
codec that silently falls back to f16 yields a *clean* arm and would fake the CUDA result.
Deltas track the bit-rate arithmetic: on the 3B, f16 → `q8_0` → `turbo3_tcq` measured
8,289 / 7,480 / 6,880 MiB against 1,792 / 952 / 364 MiB of predicted KV. No arm fell back.

## Open

- **GQA, or the Qwen-27B architecture class?** Both collapsing models are 27B Qwen
  derivatives — 65 blocks, 24/4 heads, D=256, hybrid attention. A **non-Qwen GQA ≥ 6 model**
  would separate the two, and none is on disk. This is the single most important gap.
- **No CUDA part with MMA was tested.** The only CUDA evidence is sm_60. `turboquant#311`
  reports `turbo4` V-cache corruption on an **RTX 3090** at **GQA 8:1** with runaway
  generation, fixed by `-ctv q8_0` on an identical build — same class, different codec and
  fork, so suggestive rather than confirming.
- **No mechanism.** Nothing here identifies a kernel or code path. `AFM-17` applies.
- **Fidelity is not measured.** "Clean" means not degenerate. No quality claim anywhere.
- **`AD-IQ3_S-IQ3_XXS` never loaded** — 8-line server log ending at "loading model", with
  9 GB of *host RAM* available against a 12.4 GiB file. Probable system-RAM exhaustion, which
  is a second "your box is smaller than you think" case alongside Step 0's VRAM haircut.

## Reproduction hazard

`Qwen3.8-27B-UD-IQ2_M.gguf` now returns **HTTP 404** — unsloth withdrew it when Dynamic v3.0
shipped on 2026-08-19, the same day. The measured file is pinned by md5 above but is **no
longer downloadable under that name**. Quantized-model filenames are not stable identifiers
over *time*, not merely across packagers.

## Bug A, separately

`q8_0` symmetric at D=256 on sm_60 — the 2026-08-17 silent collapse — **did not reproduce**
on buun `02f8581c65`, on one GPU or on two. The dual-GPU arm matched `RESULT_OWNERSHIP.md`
U_E in model (Qwen3.8-27B-Q6_K), codec, split mode and `GGML_CUDA_ALLREDUCE=internal`,
differing only in fork commit, and came back clean 10/10. So Bug A appears **fixed in buun
between `a8e5b5a38` and `02f8581c65`**; no commit-level isolation was attempted. This says
nothing about TheTom `f6124e9`, where the original collapse was measured and where the bisect
named `5fd308947`.
