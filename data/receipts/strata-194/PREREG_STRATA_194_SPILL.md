# Pre-registration: when the experts do NOT all fit in VRAM (Unsloth UD-IQ4_XS, 59.5 GB of experts on 4x P100), does Strata's adaptive cache beat buun's static `-ncmoe` offload with MTP?

**Registered 2026-10-06, before any row.** Mark: "I'm assuming the better test of Strata would be a larger bpw with
more spill into RAM?" -- yes.

**Prior art checked:** this campaign's `RESULT_STRATA_194.md` (all-resident IQ3_XXS: a tie, 99 % hits),
`strata-9070/` (16 GB card: 83 % hits vs static 42 %, 2.6x), INDEX L438 (llama.cpp MTP under offload 1.30-1.44x) and
the expert-spill cost curve. **What this adds:** the middle regime, partial spill on a multi-GPU box, with
speculation on both sides.

## Instrument

- **Weights:** `unsloth/Qwen3.8-Flash-Next-GGUF` UD-IQ4_XS at the revision Strata pins (`38bb39e`).
  - 3 shards (0.01 + 49.8 + 43.8 GB), downloaded and sha256-checked by Strata's setup.
  - Both engines use the same files.
- **Strata v0.1.39:** the same CUDA 12 engine as the IQ3_XXS run.
  - Installer config for `--family unsloth --model UD-IQ4_XS --gpus 0,1,2,3 --cuda 12 --vision no`, recorded from its
    json.
  - Thinking off through the shared setting.
- **buun `0b2789f23`:**
  - `-sm layer -ngl 99 -fa on -fit off -ncmoe N`, with N stepped up from 4 to the smallest that loads and serves.
  - The Flash-Next MTP head (`-md ... --spec-type draft-mtp --spec-draft-n-max 3`), `--reasoning off`, f16 KV,
    `-c 8192`.
  - The N used is recorded, together with the share of routed-expert work it keeps on the GPU, (48 - N) / 48.
- **Measurement:** as in `PREREG_STRATA_194.md` (`run194.sh`, lmx v0.1.48 remote, canonical prompts, temperature
  0, 256 tokens, 1 warmup + 3 timed, median, proxy capture, clock sampling).

## Arms

| arm | engine | prompt | starts |
|---|---|---|---|
| **S4_r** | Strata | reasoning-v1 | 2 |
| **S4_c** | Strata | code-v1 | 1 |
| **L4_r** | buun + MTP, `-ncmoe N` | reasoning-v1 | 2 |
| **L4_c** | buun + MTP | code-v1 | 1 |
| **L40_r** | buun, no drafter, same N | reasoning-v1 | 1 |

## Predictions

| # | claim | confidence |
|---|---|---|
| Q1 | Strata's decode hit rate is at least 10 pp above buun's static GPU share (48 - N) / 48 | 0.65 |
| Q2 | Strata decodes at least 10 % faster than buun + MTP on reasoning-v1 (median of S4_r starts vs L4_r starts) | 0.5 |
| Q3 | buun's MTP gain under this partial offload is below its all-resident 2.23x | 0.65 |

## Not tested

- UD-Q4_K_XL (heavier spill).
- Quality.
- Long prompts.
- Concurrency.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
