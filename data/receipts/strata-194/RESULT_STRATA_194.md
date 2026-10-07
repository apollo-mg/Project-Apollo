# Result -- on 4x P100 with the whole expert arena in VRAM, Strata (its experimental Pascal path) and our tuned buun + MTP tie on decode with the same Flash-Next IQ3_XXS weights (33.8 vs 33.4 tok/s, 1 %); buun has the better TTFT (2.3 vs 3.3 s) and uses 4 GB of RAM to Strata's 49. Strata's edge is the adaptive cache under memory pressure (the desktop run), not its kernels

**2026-10-06.** Pre-registration `PREREG_STRATA_194.md` (`ba6875ae`), no deviations.
- **Runner:** `run194.sh`, `chain194.sh`.
- **Raw:** `runs/`, including LMX JSON, proxy captures, server logs, per-second GPU clocks, Strata's engine log,
  config and setup log.
- **Summary:** `RESULT_strata194.json`.

## Setup

- **Host:** .194, 4x P100-PCIE-16GB, 2x Xeon E5-2650 v3, 121 GB RAM, driver 580.173.02.
  - Busy SM clock median 1,063 MHz in every arm, read from `clocks_*.csv`.
- **Weights (both engines):** ISTA GSQ-RCO IQ3_XXS (all 512 experts), sha256-verified against Strata's pinned
  revision.
- **Strata v0.1.39:** its CUDA 12 engine was compiled here with CUDA 12.4 + gcc-13, and it works on sm_60.
  - The installer config: 4-GPU layer split, `--remote-expert-opt`, KV streaming, `--spec 4 --spec-min-p 0.5`, its
    own MTP layer with q2_0 experts.
  - Thinking off through its shared setting (deleted after).
- **buun `0b2789f23`:** the 10-01 split-conc T3 recipe.
  - `-sm tensor -ts 1,1,1,0.75 -fa on -ngl 99`, with `-md mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type
    draft-mtp --spec-draft-n-max 3`.
  - `--reasoning off`, f16 KV, `-c 8192`.
- **Measurement:** `lmx` v0.1.48 remote on localhost; canonical prompts; temperature 0; 256 tokens; 1 warmup + 3
  timed, median. Every arm passed the content gate and returned 256 tokens; the drafter was active in every MTP arm.

## Results

| arm | tok/s (median) | samples | TTFT ms | prompt | accepted / drafted | tokens per pass |
|---|---:|---|---:|---:|---|---|
| **Strata, reasoning, start 1** | 33.3 | 32, 33.3, 33.3 | 3,294 | 307 | 167/240, 169/230, 171/229 | 2.88-3.01 |
| **Strata, reasoning, start 2** | 34.3 | 33.6, 34.3, 35.3 | 3,305 | 305 | 174/233, 174/227, 172/215 | 3.05-3.12 |
| Strata, code | 32.7 | 32.7, 32.2, 33.3 | 2,827 | 240 | 168/234, 167/238, 167/228 | 2.88-2.91 |
| **buun + MTP, reasoning, start 1** | 33.1 | 35.1, 32.8, 33.1 | 2,329 | 305 | 183/215, 179/228, 178/229 | 3.28-3.51 |
| **buun + MTP, reasoning, start 2** | 33.7 | 33.7, 30.5, 34.5 | 2,303 | 306 | 182/218, 174/221, 182/216 | 3.12-3.46 |
| buun + MTP, code | 33.1 | 33.3, 33.1, 31 | 2,076 | 241 | 179/225, 178/228, 176/235 | 3.20-3.32 |
| buun, no drafter | 15.0 | 15, 14.5, 15.1 | 2,041 | 305 | - | 1 |

- **Tokens per pass** = 256 / (256 - accepted).
- **Strata's decode expert cache hit rate:** 98.7-99.7 % over 12 requests. ~0 % of routed experts went over PCIe.
- **RAM after load:** Strata 49 GB used (72 available), buun 3-4 GB.
- **VRAM:** Strata 13.1-15.8 GB per card, buun 14.0-15.0.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | Strata's hit rate at least 95 % | **holds** (98.7-99.7 %) |
| P2 | Strata faster than buun + MTP on reasoning-v1 | **holds by the registered rule, but it is a tie:** 33.8 vs 33.4. The 1 % gap is inside the spread of either engine's samples (30.5-35.3). |
| P3 | MTP at least 1.4x for buun (fully resident) | **holds:** 2.23x (33.4 vs 15.0) |

## What it means

- **When the experts fit in VRAM, Strata's speed comes to the same thing as tuned llama.cpp + MTP.**
  - Strata runs slightly faster passes (~11.3/s vs ~9.9) but accepts fewer drafts (0.74 vs 0.82; its MTP layer's
    experts are q2_0, and it stops drafting below p 0.5).
  - buun's Q8_0 MTP head gets more tokens per pass (3.3-3.5 vs 2.9-3.1).
- **Read with the desktop run (`strata-9070/`), Strata's real contribution is the adaptive expert cache under memory
  pressure.**
  - On 16 GB of VRAM it served 83 % of expert lookups from the GPU and was 2.6x llama.cpp's static offload.
  - On 64 GB, where everything fits, there is nothing for the cache to win (99 % hits) and the engines tie.
  - The port worth considering for llama.cpp/buun is the cache (BACKLOG N20), not the kernels.
- **Strata's P100 path works.** It compiles with CUDA 12.4 + gcc-13 (not their tested 12.8/12.9) and produces
  coherent answers. These are the first P100 numbers for it, against their "not measured".
- **TTFT:** buun 2.0-2.3 s, Strata 2.8-3.3 s (a 240-307-token prompt).
- **Side note:** buun + MTP on GSQ-RCO IQ3_XXS decodes 33.4 tok/s, above the 10-01 UD-Q2_K_XL figure (27.4) on the
  same recipe. That is a different weights file, so it is not a like-for-like comparison.

## Not established

- Strata with a better MTP head, which could move its acceptance.
- Long contexts.
- Concurrency.
- Strata's IQ3_S / UD-IQ4_XS packs.
- Quality.
- Clock sensitivity (both engines were measured at 1,063 MHz).
- **Nothing was submitted.**

## Community report posted (Mark's OK, 10-06)

- **The PR:** Niko1221/Strata#1192, "Community benchmark: 4x Tesla P100 16 GB (Pascal), IQ3_XXS, CUDA 12 engine",
  from `apollo-mg:community-4x-tesla-p100`. Results only: README + `runs.json` + client timings + `strata_bench.py` +
  the two canonical prompts.
- **Folder:** `bench/results/2026-10-06-community-4x-tesla-p100/`. The draft is in `strata_pr/`.

**Landed (2026-10-07):** the community report from PR #1192 is in Strata v0.1.40.2 as
`bench/results/2026-10-06-community-4x-tesla-p100/`, with authorship kept and a row in `bench/results/COMMUNITY.md`. The
maintainer closed the PR and copied the folder in by hand. Raw dumps and logs were trimmed; the folder's TRIMMED.md lists
them.
