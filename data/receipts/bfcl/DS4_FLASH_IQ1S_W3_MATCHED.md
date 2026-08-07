# DeepSeek-V4-Flash IQ1_S on BFCL v4 parallel family — matched into leg W3

**Date:** 2026-08-07. Run completed on `.194` at 06:29 (`rc=0`). Started 2026-08-03 17:41:50 —
**~85 h of generation.** An earlier 08-03 15:56 attempt died `rc=1` at the generate step.

## The run did not do what the driver asked

The driver wrote a 35-ID-per-category subset to `test_case_ids_to_generate.json`, but the harness
**ignored it and ran the full 200 per category** — 400 items, not 70. That is the 85 h.

```
BFCL_v4_parallel_score.json           {"accuracy": 0.515, "correct_count": 103, "total_count": 200}
BFCL_v4_parallel_multiple_score.json  {"accuracy": 0.17,  "correct_count": 34,  "total_count": 200}
```

The `total_count: 200` is the tell. It went unnoticed because 51.5 % / 17.0 % are plausible-looking
numbers; neither is a multiple of 1/35 (18/35 = 51.43 %, 6/35 = 17.14 %), which is what surfaced it.

**As logged, the DS4 numbers were not comparable to the leg W3 reference**, which is a seed-42
201-item subset (`subset_ids_used.json`: parallel 35, parallel_multiple 35). Different item set,
different denominator.

## Recovery — no re-run needed

Because the harness ran the *superset*, every leg-W3 reference item was answered. Re-scoring DS4 on
exactly the 35+35 seed-42 IDs gives a properly matched three-way comparison. BFCL score files list
only failures, so an ID absent from the failure list is correct; all 35 reference IDs per category
verified in-range (0..199) with matching prefixes before relying on that.

| category | n | Puzzle-75B | Qwen3.6-27B | **DS4-Flash IQ1_S** | DS4 on full 200 |
|---|---|---|---|---|---|
| parallel | 35 | 8.6 % | 91.4 % | **48.6 %** | 51.5 % |
| parallel_multiple | 35 | 8.6 % | 80.0 % | **20.0 %** | 17.0 % |
| **parallel family** | **70** | **8.6 %** (6/70) | **85.7 %** (60/70) | **34.3 %** (24/70) | — |

DS4-Flash at IQ1_S sits **between** the two: ~4× Puzzle-75B's parallel-family rate, ~0.4× Qwen's.

## Free result from the failure

The accidental full-200 run is an unbiased check on the seed-42 subset itself. Subset vs full:
48.6 % vs 51.5 % (parallel), 20.0 % vs 17.0 % (parallel_multiple) — within ±3 pp on n=35, where one
item is 2.9 pp. **The 35-item subset is representative**, which retroactively supports every leg-W3
number that rests on it. That was not something we had evidence for before.

## Limits

- **K=1, temp 0.** Per `agent-benchmark-determinism`, temp-0 on this fleet is not reproducible; this
  is an existence proof, not a rate.
- IQ1_S is an extreme quant. Nothing here separates *DeepSeek-V4-Flash the architecture* from
  *IQ1_S the quantization* — same quant-vs-architecture confound left open for Puzzle in leg W3.
- Served `-c 16384 --numa distribute` on the `.194` quad-P100 (2×Xeon E5-2650v3, 64 GB DDR4-2133).
  Throughput logged at ~1.13 t/s cold / ~5.2 t/s warm. Fleet is configured 150 W / 1063 MHz; GPUs
  read 150 W limit at idle-check time, but clock state *during* the run was not sampled.
- No McNemar here — the leg-W3 pairing script compares Puzzle vs Qwen. A DS4-vs-Qwen paired test on
  these 70 items is available from `bfcl_per_item.csv` plus the failure lists if wanted.
