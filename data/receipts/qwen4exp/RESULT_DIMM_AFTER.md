# Result — DIMM after-run: the RAM doubled bandwidth, prefill followed, decode did not

**Run + scored 2026-09-16 ~19:45 on .194.** Before: `RESULT_DIMM_BEFORE.md` (64 GB, 4 channels).
After: 128 GB, 8 channels, **trained at 2133** (P-D1 held — no 1866 clock-drop despite the mixed rank).
Both at GPU 1189/250. Same driver sha `8b11667589c5a05b`, so before/after are byte-identical code.
This is a **clean channel-doubling read** — no clock confound.

**Data provenance (2026-09-17):** the raw after-run rows were never copied back off `.194` —
only `dimm_after.png` was. They are at `~/flashnext_res/results.jsonl` on `.194` (a home path,
so the 09-16 BMC shutdown did not touch them), pending retrieval into
`dimm_after_results.jsonl` here alongside `dimm_before_results.jsonl`. Every number in this
receipt was scored from those rows by `tools/score_dimm.py` at the time of the run; until the
file lands, the scoring is not independently re-runnable from this repo. Flagged rather than
left as a dangling reference.

## The headline

**The hardware upgrade did exactly what it promised. The thing we bought it for barely moved.**

| metric (full-spill, rung 48) | before | after | change |
|---|---:|---:|---:|
| node-local bandwidth (triad) | 22.68 | **40.16 GB/s** | **+77%** |
| first-touch bandwidth (triad) | 45.14 | **80.28 GB/s** | **+78%** |
| **prefill** tok/s @ctx 3600 | 32 | **55** | **+71%** |
| **decode** tok/s @ctx 3600 | 7.54 | **8.36** | **+11%** |
| **decode** tok/s @ctx 1800 | 8.50 | **8.68** | **+2%** |

Bandwidth ~1.77x. Prefill tracked it (bandwidth-bound). **Decode did not.**

## Prediction scorecard

| id | prediction | result |
|---|---|---|
| **P-D1** | 8 DIMMs train at 2133, not 1866 | **CONFIRMED** — 2133 across all 8, mixed rank and all |
| **P-D2** | node-local triad ≥ 35 GB/s | **CONFIRMED** — 40.16 (the "1R interleaving penalty" showed as ~1.77x not 2x, exactly as budgeted) |
| **P-D3** | first-touch ≥ 70 GB/s | **CONFIRMED** — 80.28 |
| **P-D4** | control: cross-socket stays 7.00 ±10% | **FALSIFIED (informative)** — rose 7.00 → 12.79. The cross-socket path is not purely QPI-bound; the destination node's doubled channels help even across the socket. |
| **P-D5** | **THE FORK — rung-48 decode rises ≥ ~27%** if spill is bandwidth-bound | **FALSIFIED** — predicted ≥ +26/+27% (→10.73/9.58), got **+2% / +11%**. Spill decode is **not** bandwidth-bound. |
| **P-D6** | control: rung-2 decode stays ±5% | **CONFIRMED** — +0.1% / +1.0% / -0.0% |

## The finding: spilled *decode* is not bandwidth-bound; spilled *prefill* is

The whole campaign framed the `-ncmoe` spill penalty as a bandwidth exchange rate (effective 12-23 GB/s).
This run falsifies that **for decode**: bandwidth ~doubled and decode moved +2-11%, while prefill on the
same spilled experts moved +36-71%. The split is mechanistic:

- **Prefill** pushes many prompt tokens through the spilled experts in a batch — large, amortized,
  sequential reads. That *is* bandwidth-bound, so doubling the channels nearly doubled it.
- **Decode** processes one token at a time. The hot/active experts largely fit in the 64 GB page cache
  already (so the pre-upgrade run was **not** SATA-paging-bound, contra my in-flight guess), and the
  per-token expert read is small and latency-sensitive. More *throughput* doesn't fix a latency-bound,
  already-resident working set. So decode barely moved.

**You cannot buy your way out of the spill decode penalty with memory bandwidth.** That is the opposite of
the tidy "more channels → faster serving" instinct, and it's the reason preregistering P-D5 was worth it.

## Was the RAM worth it?

Honestly: **yes for capacity and prompt-heavy work, no for spilled-decode serving.**
- **Capacity:** 128 GB unlocks models that didn't fit (e.g. the 111 GB EXL3 spill question). Real.
- **Prefill / prompt-heavy** (long context, RAG, batch): +36-71% on spilled configs. Big win.
- **Decode tok/s on spilled models** (steady-state serving): +2-11%. Modest — do not upgrade RAM *for this*.

## Housekeeping

GPU clock is at the out-of-spec 1189/250 (matched for the campaign). Restore to production 1063/150 when done.
