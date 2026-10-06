# Result -- heavy spill (Unsloth UD-Q4_K_XL, 77 GB of experts, ONE P100): Strata 19.3 tok/s vs buun + MTP 13.5 on the same card (1.43x, just short of the registered 1.5x); buun on all four cards + MTP is faster than both (21.9)

**2026-10-06.** Pre-registration `PREREG_STRATA_194_Q4XL.md` (`29931fd6`), no deviations.
- **Chain:** `kit/q4xl_chain.sh`.
- **Raw:** `runs/*_Q_*`, `runs/strata_config_q4xl.json`, `runs/strata-setup-q4xl.log`, `runs/strata-engine-q4xl.log`.

## Setup

- **Weights:** UD-Q4_K_XL at `38bb39e`, 4 shards, sha256-checked by Strata's setup (rc 0).
- **Strata (setup's config, one GPU):** `--resident-budget-gib 71`, `--max-context 32768`, `--kv int8`, `--spec 4
  --spec-min-p 0.5`, expert cache auto.
  - Its log: "expert cache 2815 slots, 8.21 GiB of VRAM", i.e. **11.5 % of the 24,576 experts**, pre-filled from the
    shipped profile.
  - About 70 GB of RAM in use after load.
- **buun `0b2789f23`, one card:** auto-fit (`-fitt 4096`): "with only dense weights in device memory there is a total
  surplus of 1964 MiB". So almost every expert stays in host memory (the CUDA0 buffer is 6.5 GB), plus the MTP head
  at draft 3.
- **buun, four cards:** surplus 46,032 MiB against ~77 GB of experts.
- **All arms:** SM clock 1,063 MHz busy, content gate passed, 256 tokens.

## Results

| arm | tok/s (median) | samples | TTFT ms | accepted/drafted |
|---|---:|---|---:|---|
| **Strata, one card, reasoning, start 1** | 19.2 | 19.3, 19, 19.2 | 5,423 | 179/208, 180/210, 182/208 |
| **Strata, one card, reasoning, start 2** | 19.4 | 19.5, 19.4, 19.3 | 6,177 | 180/206, 180/207, 178/209 |
| Strata, one card, code | 18.6 | 18.5, 18.6, 19 | 5,252 | 170-173/208-213 |
| **buun + MTP, one card, reasoning, start 1** | 13.5 | 13.7, 13.4, 13.5 | 16,151 | 182-183/214-217 |
| **buun + MTP, one card, reasoning, start 2** | 13.5 | 13.7, 13.5, 13.5 | 11,650 | 181-182/218-221 |
| buun + MTP, one card, code | 15.0 | 15, 14.8, 15.3 | 10,690 | 182-185/208-217 |
| buun, one card, no drafter | 10.5 | 10.3, 10.5, 10.5 | 14,178 | - |
| **buun + MTP, four cards, start 1** | 21.5 | 22.1, 21.5, 21.4 | 8,272 | 183-184/212-214 |
| **buun + MTP, four cards, start 2** | 22.2 | 22.2, 22.2, 22.4 | 7,174 | 183-184/212-214 |

**Strata's decode hit rate:** 65.8-66.4 % warm on reasoning and 67.6-68.6 % on code. The first request of each start
was 52.5-56.0 %.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | Strata on one card at least 1.5x buun + MTP on the same card | **does not hold:** 19.3 / 13.5 = **1.43x** |
| P2 | Strata's warm hit rate below 90 % on one card | **holds:** ~66 % |
| P3 | buun's one-card MTP gain below its 1.19x at partial spill | **does not hold:** 13.5 / 10.5 = **1.29x** |
| P4 | buun + MTP on four cards faster than Strata on one card | **holds:** 21.9 vs 19.3 |

## What it means

- **Strata's lead shrinks as spill deepens:** 1.86x at partial spill on 4 cards, then 1.43x at heavy spill on one card.
  - With 11.5 % of the experts cached it still catches two thirds of the lookups.
  - It keeps its MTP working (~3.3 tokens per pass), and its TTFT is half buun's.
  - But a third of the expert work now runs on the 2014-era Xeons either way.
- **buun's MTP gain did not collapse here (1.29x),** against 1.19x at partial spill. Two points, different cards and
  different files: there is no trend to draw yet.
- **The practical answer on .194:** for UD-Q4_K_XL, plain buun across all four cards + MTP (21.9 tok/s) beats Strata on
  the one card its setup allows (19.3). Strata's 4-card split needs ~135 GB of RAM by its own rule, and this box has
  121.5 GiB. Strata stays ahead wherever it can use all four cards (UD-IQ4_XS: 37.2 vs 20.0).
- **For the series** (all matched on speculation):

  | condition | Strata vs buun + MTP |
  |---|---:|
  | everything in VRAM (IQ3_XXS, 4 cards) | 1.0x |
  | partial spill (UD-IQ4_XS, 4 cards) | 1.86x |
  | heavy spill (UD-Q4_K_XL, 1 card each) | 1.43x |

## Not established

- Strata on four cards with this file (outside its RAM rule; not run without Mark's OK).
- NUMA-bound runs.
- Long prompts.
- Quality.
- Whether a larger Strata slot budget (`--vram-reserve`) changes the hit rate.
