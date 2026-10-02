# Result -- fully resident Flash-Next on 4x P100: layer split wins one stream, tensor split wins several (48.8 tok/s total at 4 streams), and MTP pays only for a single stream. Under tensor split MTP nearly doubles single-stream speed (14.3 -> 27.4), because it gives each card more work per synchronisation.

**2026-10-01.** Pre-registration `PREREG_SPLIT_CONC.md` (`7187fd2`), with Deviation 1 (`T3` reran at `-ts 1,1,1,0.75`
after its drafter OOM'd GPU 3). Runner `run_split_conc.sh`, probe `conc_probe.py`, analysis `analyze_split_conc.py`,
output `RESULT_split_conc.json`.

- **Raw:** `raw/rows.jsonl` (both passes; pass 2 is the measurement), `raw/refs.jsonl`, `raw/run.log`,
  `raw/sc_T3_oom.log`.
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz, buun `0b2789f23`. Flash-Next UD-Q2_K_XL fully resident
  (`-ngl 99`, 49/49 on GPU), `-c 16384 -np 4`, f16 KV, thinking off. The per-layer embedding shard was pre-read
  before every cell (the page-fault control).
- **Correctness:** every cell passed G0 (count to 20). **Every cell's first 64 tokens are identical to layer split's**,
  so tensor split produced the same text: no sign of the NaN-logit bug that got it disabled upstream, on this build.

## Results (pass 2; decode tok/s per stream, and total including prompt)

| streams | **L0** layer | **L3** layer + MTP | **T0** tensor | **T3** tensor + MTP (`-ts ..,0.75`) |
|---:|---|---|---|---|
| 1 | 21.1 / **19.3 total** | 25.5 / 22.5 | 14.3 / 13.4 | **27.4 / 24.9** |
| 2 | 9.85 each / 18.7 (pass 1: 16.8 / 30.3) | 12.5-13.3 / 23.3 | 14.5 each / **27.0** | 10.1-10.8 / 18.9 |
| 4 | 9.84 each / 36.3 | 6.3-6.7 / 23.2 | 13.5 each / **48.8** | **all HTTP 500** ("Compute error") |

MTP acceptance was 0.60-0.70 throughout.

## Registered verdicts

| # | claim | result |
|---|---|---|
| S1 | parallel streams pay (layer, no MTP): 4 streams >= 1.6x one | **holds.** 1.88x (19.3 -> 36.3) |
| S2 | the 8-token limit holds for MoE: L3 at 4 streams fails or totals less than at 2 | **holds, narrowly.** 23.19 vs 23.32, no errors. On tensor split (T3) 4 streams fail outright |
| S3 | even fully resident, tensor split loses at one stream | **holds.** 13.4 vs 19.3 total (14.3 vs 21.1 decode, -32 %) |
| S4 | tensor split gains more from streams | **holds.** 3.66x vs 1.88x (1 -> 4 streams) |

## What it means

**Mark's question 1: "is it sparsity that makes layer split better?"** Yes, for one stream without MTP. Each tensor-split
synchronisation (no NVLink or NCCL on the P100s; Pascal falls back to the butterfly all-reduce) carries too little
work, because only 10 of 512 experts run per token. **Give each card more work per sync, and tensor split wins:**
- with **MTP** (4 tokens verified per step), tensor split goes **14.3 -> 27.4 tok/s (1.92x)**, the best single-stream
  number measured (layer + MTP: 25.5);
- with **more streams**, it keeps per-stream speed nearly flat (14.3 -> 13.5) and reaches **48.8 tok/s at 4 streams**.

**Mark's question 2: "parallel sessions, or a proportionate decrease?"** Neither, and it depends on the split:
- **Layer split at 2 streams is unstable, not a step.** **Correction (same day):** pass 1 measured **16.8 per stream /
  30.3 total**, pass 2 **9.85 / 18.7**. The "step" first described here rested on pass 2 alone. Four streams were
  stable across passes (35.1 / 36.3 total), and so was every tensor-split cell. Layer split at 2 streams sometimes
  runs well and sometimes runs at half speed. The cause was not traced (slot assignment, or a prefill of one request
  landing in the other's decode batch, are candidates).
  **Cause found 10-02 (`RESULT_NUMA_PREFILL.md`): slot adjacency.** Pass 1 used slots {0,1}, pass 2 used {3,1}. With
  `kv_unified = false`, non-adjacent sequences cannot share a micro-batch, so each step runs two passes. `--kv-unified`
  removes the penalty. It is not NUMA (also tested).
- **Tensor split batches almost for free** from the first extra stream.

**MTP and concurrency do not mix.** MTP raises one stream's speed and lowers multi-stream totals on both splits. On
tensor split, 4 streams x 4 tokens fail with a compute error (the 16-token step, plus a GPU 3 squeezed by the
drafter), like .73's MMVQ limit on 09-30.

**Serving recipe for Flash-Next on .194:**

| use | config | speed |
|---|---|---|
| one user | tensor split + MTP | 27.4 tok/s |
| several users | tensor split, no MTP, `-np 4` | 48.8 tok/s total |
| avoid | layer split at 2 streams | unstable: 30.3 or 18.7 total across two passes |

**Caveats on the recipe:**
- Tensor split for qwen4exp is buun-only (upstream denies it).
- Tensor split disables prompt-cache reuse in buun's fork (`qwen38-splitmode`, 08-14 receipts). For agent workloads
  with long shared prefixes that matters more than raw decode, and was not measured here.

## Not established

- Why layer split at 2 streams is bistable across passes (16.8 vs 9.85 per stream).
- **Prefill was not captured.** Prompts were ~25 tokens and per-request prompt timings were not saved. The 09-28 MTP
  clock study's 6k-token cold prefill (layer split): 123-128 tok/s at 1063 MHz. Tensor-split prefill, where each sync
  carries a whole batch, was not measured.
- 3 or 8 streams; long contexts (256-token outputs, short prompts); the clock (1063 MHz only; MTP gains more at 1328).
- T3 used a different `-ts` from T0 (Deviation 1).
