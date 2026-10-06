# Result -- when the experts do not all fit (Unsloth UD-IQ4_XS on 4x P100), Strata decodes 1.86x faster than tuned buun + MTP on the same weights (37.2 vs 20.0 tok/s): its adaptive cache serves 98-99 % of expert lookups with 71 % of the experts in VRAM, while the best static placement keeps at most ~79 % of the expert weight on the GPUs and loses most of MTP's gain (1.19x vs 2.23x when resident)

**2026-10-06.** Pre-registration `PREREG_STRATA_194_SPILL.md` (`1b7cf797`), with Deviations 1 and 2 (`f4956f0f`,
`69180242`), both registered before any buun row.
- **Chains:** `spill_chain.sh` (S4 arms + the failed `-ncmoe` passes) and `spill_chain3.sh` (auto-fit buun arms).
- **Raw:** `runs/`, including Strata's engine log and config for this pack, and its setup log.
- **Summary:** `RESULT_strata194_spill.json`.

## Setup

- **Weights:** `unsloth/Qwen3.8-Flash-Next-GGUF` UD-IQ4_XS at Strata's pinned revision, 3 shards, hash-checked by
  Strata's setup. Both engines use the same files.
- **Host:** .194, 4x P100, SM clocks 1,063 MHz busy in every arm.
- **Strata v0.1.39:** the same CUDA 12 engine as `RESULT_STRATA_194.md`.
  - Installer config: 4-GPU layer split, `--remote-expert-opt`, `--spec 4 --spec-min-p 0.5`, its own MTP layer, int8
    KV, 32K context.
  - Expert cache: 4,397 / 4,677 / 4,534 / 3,865 slots on GPUs 0-3, i.e. **17,473 of 24,576 experts (71 %)**.
  - 64 GB of RAM used after load.
- **buun `0b2789f23`, after Deviation 2:**
  - llama.cpp's automatic fit, `-fit on -fitt 1024,1024,1024,4096 -sm layer -fa on -c 8192`, with the Flash-Next MTP
    head at draft 3 and `--reasoning off`.
  - The fit log: "with only dense weights in device memory there is a total surplus of 46762 MiB", against 59.5 GB of
    experts. So at most **~79 %** of the expert weight can stay on the GPUs; whole-layer placement leaves somewhat
    less.
  - Loaded: 12.7 / 14.3 / 14.6 / 8.1 GB on GPUs 0-3, 41 GB CPU-mapped (which includes the per-layer embedding table).
- **Measurement:** `lmx` v0.1.48 remote, canonical prompts, temperature 0, 256 tokens, 1 warmup + 3 timed, median,
  proxy capture. Every arm passed the content gate and returned 256 tokens.

## Results

| arm | tok/s (median) | samples | TTFT ms | accepted / drafted | tokens per pass |
|---|---:|---|---:|---|---|
| **Strata, reasoning, start 1** | 37.1 | 37.1, 37.7, 36.7 | 3,628 | 177/212, 183/213, 178/213 | 3.25-3.51 |
| **Strata, reasoning, start 2** | 37.3 | 37.5, 37.3, 37.2 | 3,637 | 180/210, 177/209, 178/211 | 3.24-3.37 |
| Strata, code | 35.7 | 35.7, 35.9, 35.7 | 3,043 | 171/216, 171/214, 171/216 | 3.01 |
| **buun auto-fit + MTP, reasoning, start 1** | 20.0 | 20.4, 20, 18.8 | 5,276 | 183/214, 181/221, 181/219 | 3.37-3.51 |
| **buun auto-fit + MTP, reasoning, start 2** | 19.9 | 19.9, 20.2, 19.7 | 5,391 | 183/216, 183/214, 182/218 | 3.46-3.51 |
| buun auto-fit + MTP, code | 20.7 | 20.7, 20.1, 20.9 | 4,862 | 186/205, 182/217, 184/213 | 3.46-3.66 |
| buun auto-fit, no drafter | 16.7 | 16.9, 16.7, 16.7 | 4,513 | - | 1 |

- **Strata's decode hit rate per request:** 97.9-99.0 % after each start's first request. The first requests (cache
  still warming) were 93.6 / 93.7 / 95.4 %. 0.0-0.8 % of routed experts went over PCIe.
- **Failed attempts, kept as findings (Deviations 1-2):**
  - Layer split + `-ncmoe` 4-24 with the drafter: CUDA3 cannot hold the drafter, which lands on the last card while
    `-ncmoe` offloads the first N layers.
  - With `-ts 1,1,1,0.6`: CUDA1 needs a 17 GB buffer at every `-ncmoe` up to 24. A first-N static split cannot place
    this model sensibly across four 16 GB cards.

## Registered verdicts

| # | claim | result |
|---|---|---|
| Q1 | Strata's hit rate at least 10 pp above buun's static GPU share | **holds:** 97.9-99.0 % (warm) against at most ~79 %. Even the cold first requests (93.6 %) clear it by 15 pp. |
| Q2 | Strata at least 10 % faster than buun + MTP on reasoning-v1 | **holds:** 37.2 vs 20.0, **1.86x**. Acceptance is the same (~0.84 both), so the gap is pass speed. |
| Q3 | buun's MTP gain under partial offload is below its all-resident 2.23x | **holds:** 1.19x (19.95 vs 16.7) |

## What it means

- **This is the regime the adaptive cache is for, and it pays: 1.86x on the same weights and drafts.**
  - ~71 % of the experts, chosen by use, catch ~98-99 % of lookups.
  - A static placement holding the same order of weight covers only its share of the work, and every miss is
    computed on the CPU, where a multi-token MTP verify is expensive. That is why buun's MTP gain collapses to 1.19x
    under offload (cf. INDEX L438) while Strata's survives (~3.3 tokens per pass at full speed).
- **The three runs together:**

  | condition | Strata vs llama.cpp | why |
  |---|---:|---|
  | everything fits (IQ3_XXS) | 1.0x (tie) | nothing for the cache to do |
  | partial spill (UD-IQ4_XS) | 1.86x | the cache keeps hot experts on the GPU |
  | heavy spill (desktop, 16 GB) | 2.6x | the same, plus static offload's verify penalty |

- **Strata is faster on the bigger pack than on IQ3_XXS** (37.2 vs 33.8): its MTP is accepted more often on the better
  quant (~0.84 vs 0.74), and the cache absorbs the spill.
- **llama.cpp's static options are themselves a finding.** First-N `-ncmoe` cannot place a 4-GPU layer split under
  pressure. Only the automatic fit works, and it leaves 1-2 GB per card unused (also seen in `glm53-flash/`).
- **For BACKLOG N20:** this measured skew on Flash-Next (71 % of experts -> 98-99 % of lookups) is the number to
  compare other MoEs' routing traces against.

## Not established

- UD-Q4_K_XL (heavier spill).
- buun with a hand-tuned `-ot` placement (e.g. the hot experts pinned by a profile; that is close to what Strata
  automates).
- Long prompts and concurrency on this pack.
- Quality.
- **Nothing was submitted.**
