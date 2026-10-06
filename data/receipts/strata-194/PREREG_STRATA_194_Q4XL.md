# Pre-registration: under heavy expert spill (Unsloth UD-Q4_K_XL on ONE P100, 77 GB of experts), how does Strata compare with buun + MTP on the same card and file, and with buun spread over all four cards?

**Registered 2026-10-06, before any row.** Mark: "I'm assuming the better test of Strata would be a larger bpw with
more spill into RAM?" and, after the partial-spill result, "We can go ahead and knock out the remaining two".

**Prior art checked:** `ledger_precheck.py "Strata UD-Q4_K_XL single GPU expert spill RAM"` -> this campaign's
receipts:
- `RESULT_STRATA_194.md`: everything in VRAM, a tie.
- `RESULT_STRATA_194_SPILL.md`: partial spill on 4 GPUs, 1.86x, speculation matched.
- `strata-9070/`: heavy spill on the desktop, 2.6x, NOT speculation matched.
- `qwen4exp/RESULT_FLASHNEXT_SPILL_LADDER.md`: llama.cpp alone, `-ncmoe` ladder.

**What this adds:** the first heavy-spill comparison with speculation matched on both sides (the desktop 2.6x had no
llama.cpp drafter), and Strata's K-quant expert path on Pascal, which its docs list as "not measured".

## Why one GPU

Strata's setup will not split UD-Q4_K_XL across GPUs on this host.
- Its rule (`unsloth_split_need_gb`, #498): a split runs without a RAM budget and needs the GGUF files plus 24 GB
  of RAM, about 135 GB. .194 reads as 121.5 GiB.
- So setup keeps one GPU, with a RAM budget of experts (recommended 71 GiB here, i.e. ~99 % of the 77 GB). The rest
  is read through the file cache.

**So the comparison is one card against one card.** It is **not** a point on the 4-GPU trend of the two earlier
results. The 4-GPU buun arm (B4) is a reference for what this box does best with llama.cpp on this file.

Forcing a 4-GPU Strata split without the budget would run outside Strata's own RAM envelope, so it is not run without
Mark's OK.

## Instrument

- **Weights:** `unsloth/Qwen3.8-Flash-Next-GGUF` UD-Q4_K_XL at Strata's pinned revision `38bb39e`, 4 shards,
  111.3 GB.
  - Size and sha256 are checked by Strata's setup against `setup.py`'s table (shard 2 `3f342f1c…`, 3 `56758f40…`,
    4 `753bda48…`).
  - Both engines read the same files.
  - The format mix (Strata's `docs/UNSLOTH_Q4.md`): experts gate/up Q4_K (Q5_K in layer 2) and down Q5_1 (Q8_0 in
    five layers); attention, shared expert, embeddings and head Q8_0; the 28.8 GB PLE table IQ4_NL.
- **Strata v0.1.39:** the engine already on .194 (`build-cuda12`, `STRATA_EXPERIMENTAL_SM60=ON`,
  `STRATA_MMQ_KQUANTS=OFF`, as released: the prompt path dequantizes the K-quant experts to FP16).
  - Config from `setup.py --family unsloth --model UD-Q4_K_XL --gpu 0 --cuda 12 --vision no --yes --no-start`,
    recorded as written: context, KV, RAM budget, spec settings.
  - Its own MTP (`--spec 4 --spec-min-p 0.5` if setup writes it, as before).
- **buun `0b2789f23`** (`~/buun-0b278/build_sm60`), as in the spill test:
  - **B1 (one card):** `CUDA_VISIBLE_DEVICES=0`, `-fa on -fit on -fitt 4096 -c 8192`, the Flash-Next MTP head
    (`mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf`, 2.79 GB) at draft 3, `--reasoning off`. The 4 GB margin leaves room
    for the drafter, as on the drafter card in the spill test.
  - **B1n:** B1 without the drafter.
  - **B4 (four cards):** `-sm layer -fa on -fit on -fitt 1024,1024,1024,4096` + the MTP head at draft 3, identical to
    the spill test's L4 arms.
- **Placement and threads:** each engine's defaults, no NUMA binding. On the dual-socket host the experts land by
  first touch for both engines (cf. `numa-distribute-is-threads-only`).
- **Host:** .194, 4x P100, clocks recorded per arm. A fresh server per arm (PID recorded, killed by PID).
- **Measurement:** `lmx` v0.1.48 remote via `kit/run194.sh`, as in the earlier runs.
  - Canonical prompts, temperature 0, 256 tokens, 1 warmup + 3 timed, median.
  - Proxy capture of drafted/accepted counts.
  - Content gate: non-empty `content`, 256 tokens.
  - Strata's decode hit rate per request from its engine log, as in the spill test.

## Arms (chain order)

S1_r1, B1_r1, S1_r2, B1_r2 (reasoning-v1, two starts each, interleaved), S1_c, B1_c (code-v1), B1n_r (reasoning, no
drafter), B4_r1, B4_r2 (reasoning).

## Predictions

| # | claim | confidence |
|---|---|---|
| P1 | Strata on one card is at least 1.5x buun + MTP on the same card (reasoning-v1, median of the two starts each) | 0.55 |
| P2 | Strata's warm decode hit rate on one card is below 90 % (a ~10 GB cache against 77 GB of experts) | 0.7 |
| P3 | buun's MTP gain on one card (B1 / B1n) is below its 1.19x at partial spill | 0.65 |
| P4 | buun on four cards + MTP (B4) is faster than Strata on one card (S1) | 0.55 |

**Gate:** if Strata's K-quant decode fails on sm_60 (no load, garbage, empty content), S1 is reported as failed with
the error, and P1, P2 and P4 are not scored.

## Not tested

- Strata split over four cards on this file (outside its RAM rule).
- `STRATA_MMQ_KQUANTS=ON` (prompt speed only).
- Long prompts, concurrency.
- Quality (Strata's docs report 97.5-99 % same greedy tokens as llama.cpp on short answers).
- A NUMA-bound configuration.

## Disk

- .194 has ~125 GB free, after Kolibri K5 deletes its Q3_K_S.
- The 111.3 GB download leaves ~10 GB with the pack. Nothing else is deleted for this run.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
