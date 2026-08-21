# Pre-registration — does `-np` batching change everything?

**2026-08-21, before any arm ran.**

## Why this is the highest-value untested assumption

**Every throughput number this project owns was taken at `-np 1`, one request at a time** — the
2v4 result, the fleet memory, the A1 sizing, all of it. The fixture itself issues items
strictly sequentially.

At batch 1 decode is **memory-bandwidth-bound**: the whole model is read per token. At batch N
the *same* weight read serves N sequences. If the P100s are bandwidth-bound rather than
compute-bound at 150 W, aggregate throughput should scale close to linearly for small N — which
would mean **every fixture run so far has been leaving a multiple on the table**, and it would
matter more than the 1.70× the 2×2 scheduling change bought.

## Stack

`.194`, GPUs **0,1** (same socket, `PHB`), NUMA-pinned to node 0, 1063 MHz / 150 W.
`llama_stock/build_puzzle` server (sm_60 carve-out verified), `Qwen3.8-27B-Q6_K`, `-sm tensor`,
`GGML_CUDA_ALLREDUCE=internal`, `-c 16384`. Arms: `-np` ∈ {1, 2, 4, 8}; client fires exactly
`-np` concurrent requests, **each with a distinct prompt** so prompt-cache hits are not measured
as throughput. 256 tokens per request, 2 reps.

## Predictions

| # | prediction | conf |
|---|---|---|
| **N1** | Aggregate t/s at `-np 4` ≥ **2.5×** the `-np 1` figure | 0.70 |
| N2 | Per-request t/s **falls** as `-np` rises (latency worsens while throughput improves) | 0.85 |
| N3 | Scaling is sub-linear and flattening by `-np 8` | 0.75 |
| N4 | `-np 1` reproduces 13.00 t/s from `RESULT_2V4.md` within 10 % | 0.80 |
| **N5** | **`-np 4` on ONE 2-GPU pair beats the 26.03 t/s aggregate of two concurrent `-np 1` jobs** | 0.55 |

**N5 is the one that would rewrite this morning's conclusion.** If a single batched server beats
two separate jobs, the scheduling rule becomes "batch within a job", not "run two jobs" — and the
2×2 finding, while still true as measured, stops being the operative advice.

## Falsification notes written in advance

- If scaling is near-flat, these P100s are **compute-bound at 150 W**, not bandwidth-bound. That
  would be a genuinely important fact and would explain why the clock pin binds so hard.
- **Batching is not free for benchmarking.** Concurrent slots share a KV cache budget
  (`-c 16384 / -np 8` = 2048/slot), and our calibration items have run to 6144 tokens. Any
  throughput win has to be weighed against per-slot context, and for `tier_cal` that may make
  batching unusable regardless of the number.
- Distinct prompts are used deliberately; identical ones would measure the prompt cache.
