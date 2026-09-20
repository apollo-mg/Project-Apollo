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

---

## GLM-5.3 is blocked upstream, not on buun -- 2026-09-19

Asked buun directly about `0xSero/GLM-5.3-Flash-EXL3-Spark`, whose card reports MTP layer 45
non-functional pending checkpoint-key remapping **and runtime support for the `mul1` codebook**.

**His answer: "I don't have GLM-5.3 support at all."** He is deliberately waiting because there
are **three competing GLM-5.3 implementations upstream** in llama.cpp and he does not want to
optimise one, then fall out of sync when a different one lands.

**Consequences for this fleet:**

- **Any GLM-5.3 work through buun's tree is blocked on an upstream decision**, regardless of quant
  format. Not an EXL3 problem, not a `mul1` problem, not a Bonsai-style packaging problem.
- The Spark card's `mul1` runtime blocker is **not** evidence of a gap in buun's EXL3 path. Our own
  O2 is RETIRED: MTP engages on a `mul1` EXL3 quant in his tree at GGUF's acceptance rate
  (0.693 vs 0.688), buying 1.24x. The support exists; the architecture does not.
- **Correction to how this was first framed:** I described it to Mark as "a real, specific interop
  gap" in buun's fork. That was wrong twice over -- the mul1 runtime path works, and the actual
  blocker is one level lower (no GLM-5.3 at all) and outside buun's control.

**Watch item:** which GLM-5.3 implementation upstream adopts. Until then, GLM-5.3 is not a
candidate for any fleet campaign.


---

## Supply roughly doubled in a week, and the naming convention changed -- 2026-09-20

HuggingFace search for `exl3`: **2,045 models**, against the "at least 1,000" recorded above a
week earlier. No longer a turboderp monoculture -- Mia-AiLab, MikeRoz, bullerwins, Lygodactylus,
erlidev, GestaltLabs, diffbot, r0b0tlab, neko-legends, brandonmusic and dealignai are all
publishing, at sizes from 6B to 332B.

### Quantizers are publishing to VRAM TARGETS, not quant levels

| repo | what the name promises |
|---|---|
| `GestaltLabs/Qwen3.8-27B-EXL3-11.5GB` | a size |
| `diffbot/DeepSeek-V4.1-Flash-EXL3-2.0bpw-2x-RTX-PRO-...` | a specific card pair |
| `0xSero/GLM-5.3-Flash-EXL3-Spark` | a specific machine (DGX Spark, 128 GB) |
| `MikeRoz/GLM-5.3-Flash-Uncensored-4.05bpw-h6` | an exact bitrate plus head bits |

**This is a format-level advantage and it is the direct answer to the GGUF label problem.**
`lowbit-ladder/FINDING_LABEL_VS_REAL_BPW.md` measured `IQ3` spanning **2.97 to 3.74 scored bpw
across packagers -- a 26% spread under one name**. EXL3's arbitrary bitrate means a publisher can
name the target instead of the recipe, so **"will it fit" is answerable from the repo name**.

### The binding constraint has moved

GLM-5.3 is abundantly quantized in EXL3 -- turboderp, Mia-AiLab, neko-legends, MikeRoz,
bullerwins and brandonmusic all ship one. **buun has no GLM-5.3 support at all** (2026-09-19,
waiting on upstream to choose among three competing implementations).

So for EXL3-through-llama.cpp the limit is no longer *"has anyone quantized it"* (O9, retired) but
**"does the runtime know the architecture."** That is a different objection and it is not on
buun -- see the GLM-5.3 section above.
