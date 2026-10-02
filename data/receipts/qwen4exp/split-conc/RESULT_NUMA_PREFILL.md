# Result -- the layer-split 2-stream "bistability" is slot adjacency, not NUMA: with a per-slot KV cache, two requests on non-adjacent slots are decoded in separate passes (0.60x); `--kv-unified` removes it. And tensor split prefills Flash-Next 2.2x faster than layer split at the default ubatch, reaching 430 tok/s at 8k with ub 4096 (3.3x layer's best measured 8k).

**2026-10-02.** Pre-registration `PREREG_NUMA_PREFILL.md` (`69dfcac8`), with Deviation 1 (exploratory forced-slot
test, `e77ecc99`, reading rule fixed before it ran). Runner `run_numa_pf.sh` + `run_slots.sh`, probes `conc_probe.py`
(unchanged), `pf_probe.py`, `slot_probe.py`, sampler `numa_sampler.sh`, analysis `analyze_numa_pf.py`
(self-tested), output `RESULT_numa_prefill.json`.

- **Raw:** `raw_numa/`: rows, server logs, `numastat_*`, `psr_*` thread samples, `slot_rows.jsonl`.
- **Host and build:** .194, 4x P100 at 150 W / 1063 MHz, buun `0b2789f23`. Flash-Next UD-Q2_K_XL fully resident
  (49/49), f16 KV.
- **File pages held constant:** caches dropped, then shards 2 and 3 read under `--interleave=all`: 37.7 / 37.7 GB per
  node.

## Part N -- registered verdicts: NUMA is not the cause

| # | claim | result |
|---|---|---|
| N1 | bound arms stable (+/-5 %) | **does not hold.** C0 is (max deviation 1.1 %), but **C1b went slow** in passes 2-4 (18.9 / 19.5 / 19.7 after 31.4) |
| N2 | unbound reproduces the instability (max/min >= 1.15) | **does not hold.** All 12 unbound passes were fast: 31.2-31.7 (1.01x) |
| N3 | socket matters (C0 vs C1 >= 10 %) | **does not hold.** Medians 31.6 vs 31.3 |

- **Thread samples:** U1 and U2 ran their compute thread on node 0, U3 on node 1. All three ran at 31.6 tok/s.
- **For this workload the socket does not matter:** layer split, decode, file pages interleaved. AFM-28's binding rule
  came from a tensor-split benchmark and still stands there.

## The cause (Deviation 1, forced slots)

**What the server logs showed:**
- `kv_unified = 'false'`: each of the 4 slots has its own KV stream.
- **Every slow 2-stream pass used non-adjacent slots:** {0,3} in C1b, and {3,1} in 10-01's L0 pass 2.
- **Every fast one used adjacent slots:** {0,1} and {2,3}.
- **Slow streams ran at 9.85-10.3 tok/s:** about two single-token passes in series.

**Forced with `id_slot`** (2 parallel 256-token requests per pair, 2 reps, C0 binding, 10-01's L0 config):

| per-stream tok/s | {0,1} | {1,2} | {2,3} | {0,2} | {1,3} | {0,3} |
|---|---:|---:|---:|---:|---:|---:|
| default (`kv_unified = false`) | 17.3 | 17.3 | 17.3 | **10.3-10.4** | **10.3-10.4** | **10.4** |
| `--kv-unified` | 17.3 | 17.3 | 17.3 | 17.3 | 17.3 | 17.3 |

**The reading rule holds:** every adjacent pair runs >= 15, every non-adjacent pair <= 12, in both reps.
`--kv-unified` removes the penalty and costs adjacent pairs nothing.

**Mechanism, from source:**
- **The batch split:** `llama_batch_allocr::split_equal(n_ubatch, sequential)` (`src/llama-batch.cpp:538`) accepts
  "only increasing sequence ids" (`seq_id == last_seq_id + 1`) when `sequential` is set.
- **When it applies:** the KV cache (`llama-kv-cache.cpp:3036`) and the hybrid memory (`llama-memory-hybrid.cpp:94`)
  set `sequential = !unified`. A pure recurrent memory sets it always.
- **Why requests land on gaps:** llama-server maps slot N to sequence N. Two concurrent requests on slots with a gap
  between them cannot share a micro-batch, so each decode step runs two passes. A gap of one costs as much as a gap
  of two.
- **Why it looked bistable:** the server picks slots by LRU and prompt similarity. Whether a pair lands adjacent
  depends on the request history, and once a non-adjacent pattern forms it repeats.

## Part P -- prefill (registered verdicts; C0 binding, median of 3 cold requests)

| prefill tok/s | ub 512 | ub 2048 | ub 4096 |
|---|---:|---:|---:|
| layer, 2k | 132 | 219 | 218 |
| layer, 8k | 132 | **OOM** (HTTP 500) | **OOM** (HTTP 500) |
| tensor, 2k | 286 | 411 | 410 |
| tensor, 8k | **287** | **399** | **430** |

| # | claim | result |
|---|---|---|
| P1 | tensor split wins prefill at ub 512 | **holds. 2.17x** (287 vs 132 at 8k) |
| P2 | tensor gains >= 1.15x from ub 2048 | **holds. 1.39x** (8k) |
| P3 | layer does not gain >= 1.15x from ub 2048 | **not testable at 8k:** both layer cells with ub >= 2048 failed the 8k request. At 2k, ub 2048 is **1.65x** ub 512, the opposite of the premise (that losing the 4-ubatch pipeline outweighs wider kernels) |
| P4 | best 8k cell >= 163 tok/s (1.3x the 09-28 reference) | **holds. 430 tok/s**, 3.4x the 09-28 layer-split reference (123-128) |

- **The layer-split OOMs are placement, not layer split itself.** The error is `CUDA pool allocation failed (out of
  VRAM)`: under `-ts 1,1,1,0.6`, GPU 1 had 43 MiB free while GPU 3 had 6.6 GB. A `-ts` that evens out free VRAM
  would likely fit (`drafter-gates-kv-budget` pattern). It was not tested.
- **Why tensor split wins here but loses single-stream decode** (14.3 vs 21.1, 10-01): a prefill ubatch carries 512-4096
  tokens per all-reduce instead of 1. This is the same "more work per sync" effect as MTP and multiple streams.
- **The ub 4096 gain shows only at 8k** (430 vs 399): a 2k prompt is a single ubatch at either width.
- **Jabba's DeepSeek V4.1 result** (chunk width +54 % at 8k, fading with context) points the same way: a wider chunk
  pays at short-to-mid context.

## What it means

- **Serving rule: use `--kv-unified` whenever `-np` > 2.**
  - Otherwise concurrent requests that land on non-adjacent slots decode at 0.60x, depending on slot history, with
    no error or warning.
  - .73's daily driver (`-np 2`, slots 0 and 1) cannot hit it. Its recorded option B (`-np 4`) would have.
  - **Upstream default (mainline `81ff93e`, `tools/server/server.cpp:157-160`):** with `-np` unset, the server picks
    4 slots *and* sets `kv_unified = true`. **An explicit `-np N` leaves it false.** So the trap catches exactly the
    configs that set `-np` by hand, which every serving script here does.
- **Flash-Next on .194, updated recipe:**
  - tensor split, `-ub 4096`: 430 tok/s prefill at 8k;
  - with MTP: 27.4 tok/s single-stream decode (10-01, T3; MTP and `-ub 4096` were not combined here).
  - Caveats: tensor split is buun-only for qwen4exp, and disables prompt-cache reuse (08-14).
- **10-01's receipt is corrected:** its "unstable" layer-split 2-stream cell was a slot pair, not noise or NUMA.

## Not established

- `--kv-unified` with MTP, with tensor split, or at 3-4 streams. It removes the penalty for pairs; its cost
  elsewhere was not measured.
- Layer split at ub >= 2048 with an evened `-ts`.
- Prefill beyond 8k, where Jabba's data and the 128k .73 receipt both show the chunk-width gain fading.
- Whether this is reported upstream. The constraint is deliberate (consecutive streams); the serving consequence
  (a slot-history-dependent 0.60x with no warning) may not be.
