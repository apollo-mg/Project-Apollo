# Note — EXL3 supply on Hugging Face (ledger O9)

**2026-09-12**, from the HF API, sorted by downloads. Counts are what the API returns: the `search=exl3`
query hits the 1000-model page limit, so **1000 is a floor, not a total**.

## What exists

- **At least 1,000 repos match "exl3".** Top publishers by repo count: **ArtusDev 170**, **turboderp 64**,
  blockblockblock 57, UnstableLlama 53, dr-housemd 37, MetaphoricalCode 36, async0x42 32, DeathGodlike 32.
- **Most downloaded:** `brandonmusic/GLM-5.2-EXL3-TR3v4-3.5bpw-MTP78` (17,489),
  `malaiwah/Qwen3.8-27B-EXL3-K5K6-hydrated` (12,396), `turboderp/Qwen3.8-27B-exl3` (4,579 with 113 likes,
  the one this campaign uses).

## The bases this fleet runs

| base | EXL3 repos | notable |
|---|---|---|
| Qwen3.8-27B | 20 | `turboderp/Qwen3.8-27B-exl3` (ours), `Mia-AiLab/…-3.5bpw`, `malaiwah/…-K5K6` |
| Qwen3.8-Flash-Next | 5 | **`turboderp/Qwen3.8-Flash-Next-exl3`** (1,374 downloads) |
| DeepSeek-V4-Flash | 20 | several at 2.5–2.7bpw |
| GLM-4.7-Flash | 4 | `dr-housemd/GLM-4.7-Flash-exl3-4bpw-H6`, and a 3bpw |

**Flash-Next connects to the open buun thread.** turboderp publishes an EXL3 of it, and buun's
`8fcd76898` fixed EXL3 MTP scale slots specifically for Flash-Next — so that path has upstream attention
already. Whether it fits this fleet is a VRAM question for `.194`, not a supply question.

## What this does not tell us

- **Which quants use the `mul1` codebook** (format ≥ 1.x), the only ones that take the int8 path on
  sm_60. An older format-0.0.1 quant exercises only the loader and reconstruct+cuBLAS
  (`kv-tensor-split/RESULT_EXL3_SM60_INFERENCE.md`). **Check `quantization_config` per model before use.**
- **Whether a given publisher's calibration is sound.** The same caution as GGUF packagers: one label,
  several recipes.

## Verdict for O9

**Supply is not the binding constraint** for the models this fleet runs today. It would bind only for a
model nobody has quantized, which is what O8 covers — whether we can make our own.
