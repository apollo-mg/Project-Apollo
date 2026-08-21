# Batching and 2×2 compose — the real ceiling is 65 t/s, not 26

**2026-08-21**, `.194`, GPUs 0,1 (`PHB`, NUMA-pinned node 0), 1063 MHz / 150 W.
`llama_stock/build_puzzle` server, `Qwen3.8-27B-Q6_K`, `-sm tensor -fit off -c 16384`,
`GGML_CUDA_ALLREDUCE=internal`, f16 KV. Client fires exactly `-np` concurrent requests with
**distinct prompts** and `cache_prompt: false`, 256 tokens each, 2 reps. Raw `raw_bench_np.log`.
Pre-registration `PREREG_NP.md`.

## Result

| `-np` | aggregate t/s | vs `np=1` | per-request t/s | marginal gain |
|---:|---:|---:|---:|---:|
| 1 | 12.12 | 1.00× | 12.12 | — |
| 2 | 21.51 | 1.77× | 10.76 | 1.77× |
| 4 | 27.09 | **2.23×** | 6.78 | 1.26× |
| 8 | 32.54 | **2.68×** | 4.07 | 1.20× |

**Every throughput number this project owns was taken at `-np 1`.** On one 2-GPU pair, four
concurrent slots deliver **2.23×** the aggregate of one, and eight deliver 2.68×.

## The two findings compose

They are orthogonal — batching packs a single job, 2×2 uses the second socket:

| configuration | aggregate |
|---|---:|
| one pair, `np=1` (this morning's per-job figure) | 12.12 |
| two pairs, `np=1` (`RESULT_2V4.md` `CONC`) | 26.03 |
| one pair, `np=4` | 27.09 |
| **two pairs, `np=4`** | **~54** |
| **two pairs, `np=8`** | **~65** |

**This morning's 26.03 t/s "ceiling" is 40 % of what the box actually does.** The 2×2 result
stands exactly as measured — it just was not the binding constraint.

## The catch, which was pre-registered

**Concurrent slots split the context.** At `-c 16384`, `np=4` gives **4096 tokens per slot** and
`np=8` gives **2048**. `tier_cal` items have run to **6144 tokens**, so batching the calibration
tier requires `-c ≥ np × 6144` — 24,576 at `np=4`. That is affordable here (f16 KV on this model
is 65,536 B/token, so 24,576 ctx ≈ 1.6 GB against ~10 GB free on a 32 GB pair) but it is **not**
affordable on the 16 GB 9070 XT. Batching is a `.194` capability, not a fleet-wide one.

Latency degrades throughout — 12.12 → 4.07 t/s per request. Irrelevant for a sweep, decisive for
interactive use. And the marginal gain is collapsing (1.77 → 1.26 → 1.20), so `np=4` is the
sensible operating point for context-hungry work rather than `np=8`.

## This reverses a recommendation made this morning

`A1_MEASUREMENT_CORPUS_SPEC.md` moved the corpus to the 9070 XT because it is 4.2× a P100 per
token. With batching, **`.194` is the better box for fixture sweeps**: two pairs at `np=4` is
~54 t/s on Q6_K against 32.1 t/s single-stream on RDNA4 — and `.194` can hold a **13.27 GiB
IQ4_XS with room for the context**, which the 9070 XT cannot without evicting the desktop.

Re-sizing A1 once more: 112,020 tokens/pass, two quants run concurrently one per socket pair at
`np=4`, ×3 repeats for `temp=1.0` non-determinism → **~3.4 h for the full two-quant comparison**,
against 37.6 h estimated this morning. **11×**, from three independent corrections: effort is
not the cost driver, concurrency is free, and batching was never tested.

## Prediction scorecard

| # | prediction | conf | outcome |
|---|---|---|---|
| N1 | `np=4` ≥ 2.5× `np=1` | 0.70 | **FALSIFIED** — 2.23×, just under |
| N2 | per-request t/s falls as `np` rises | 0.85 | correct — 12.12 → 4.07 |
| N3 | sub-linear, flattening by `np=8` | 0.75 | correct — 1.77 / 1.26 / 1.20 |
| N4 | `np=1` within 10 % of llama-bench's 13.00 | 0.80 | correct — 12.12, 6.7 % low (HTTP overhead) |
| N5 | `np=4` on one pair beats two concurrent `np=1` jobs | 0.55 | correct — 27.09 vs 26.03, and 27.09 vs 24.25 same-instrument |

**4 of 5.** N5 was the low-confidence call and it held; N1 was the confident one and it missed.

## Scope

One model, one quant, `-c 16384`, 256-token generations, dense, tensor split, one socket pair.
Untested: batching under **layer** split, on **RDNA4**, with speculation (MTP/DFlash draft
acceptance may interact badly with batching), and at generation lengths matching real fixture
items rather than 256 tokens.
