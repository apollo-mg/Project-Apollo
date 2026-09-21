# Result -- the medium token bill on the actual campaign config: A1 is 19x cheaper than it priced itself

**2026-09-21, `.194`** (2x Tesla P100 of 4, GPUs {0,1} = the socket-0 PHB pair, `numactl
--cpunodebind=0 --membind=0`, `GGML_CUDA_ALLREDUCE=internal`, 1063 MHz / 150 W).
buun `08826ad6`, `Qwen3.8-27B-Q6_K`, `-sm tensor`, f16 KV, `-np 1`, `-fa on`, **MTP off**.
Card sampling (`temp 1.0 / top_p 0.95 / top_k 20`). `tier_cal` v0, all 16 items.
Warmup generation discarded. Raw: `tier_cal_medium_q6k_194_20260921.jsonl`.

**Prior art checked:** `ledger_precheck.py "agentic corpus judgement underspecification"` and
`"effort sweep"` -> `RESULT_EFFORT_SWEEP.md` (08-21) already established that `xhigh` costs 11.3x
`medium` and is worse. **What this adds:** that sweep ran on `AD-IQ3_XXS` on the **9070 XT**;
A1's cost basis ran at `xhigh` on **Q6_K on `.194`**. Nobody had measured `medium` on the config
the campaign will actually use, so the sizing rested on transferring a ratio across both a model
and a GPU. This measures it directly.

## The bill

| arm | n | median chars | mean | max | **median tok** | mean tok | censored |
|---|---:|---:|---:|---:|---:|---:|---:|
| answerable | 8 | 428 | 417 | 629 | **96** | 111 | **0** |
| unanswerable | 8 | 1,096 | 1,356 | 3,129 | **262** | 322 | **0** |

**Zero non-terminators**, consistent with `RESULT_EFFORT_SWEEP`'s 0/8 at `medium` (against 3/8 at
`xhigh`). Observed end-to-end throughput **12.15 tok/s** (3,468 tokens / 286 s) -- slightly under
`llama-bench`'s `tg128` 13.00 for this config, as expected since real requests carry prefill.

## Against A1's own baseline, same model and same box

| | A1 (`xhigh`) | this (`medium`) | |
|---|---:|---:|---|
| answerable median chars | 724 | **428** | 1.69x cheaper |
| unanswerable median chars | 5,090 | **1,096** | **4.64x cheaper** |
| unanswerable:answerable ratio | 7.0x | **2.56x** | |
| tokens per 240-per-arm sweep | ~521,000 | **85,920** | **6.1x fewer** |

## Sizing

At A1's working target of **240 per arm**: `240 x 96 + 240 x 262 = 85,920 tokens`.

| | A1 | now |
|---|---:|---:|
| per sweep | 18.8 h | **1.96 h** |
| two-quant comparison | 37.6 h | **1.96 h** |

**9.6x per sweep, 19.1x for the comparison.** Three independent corrections, all multiplicative:

1. **Effort.** A1 priced `xhigh`; `medium` is 6.1x fewer tokens *and* strictly better -- 0
   non-terminators against 3/8.
2. **Split mode.** A1 assumed 7.7 t/s, which is `.194` at *layer* split. Tensor split on a
   same-socket pair measures 13.00 (`splitscale/RESULT_2V4.md`, and that figure is already
   **without speculation** -- the receipt says so explicitly).
3. **Concurrency.** Two 2-GPU arms run simultaneously on `{0,1}` and `{2,3}` with zero contention,
   so a two-quant comparison costs the same wall clock as one sweep. Instrument-legal because both
   arms share the **same** partition scheme; only *varying* device count within a comparison is
   forbidden.

**A1's "this does not belong on Pascal" conclusion is void.** It rested on the 18.8 h figure, and
the 9070 XT cannot load this model at all -- 21.3 GB against a ~11.5-12 GiB practical weights
ceiling.

## What this does NOT establish

- **MTP was off.** Speculative decoding would add a measured **1.82-1.84x** on Q6_K
  (`RESULT_SPLIT_X_MTP.md`), but it is not bit-exact against non-speculative (0/12,
  `spec-decode-determinism/RESULT_SPECULATION_IS_NOT_BIT_EXACT.md`) so it stays off for a
  comparison. The ~2 h figure is the honest MTP-off cost.
- **n=8 per arm.** These are medians of eight items. The *spread* is what a real sweep will differ
  on -- the unanswerable arm already ranges 650 to 3,129 chars.
- **tier_cal v0 items only.** The argus v2 judgement corpus is a different construction and its
  per-item bill is unmeasured; do not transfer these medians to it without measuring.
- **Q6_K only.** Lower quants are the point of the comparison and may deliberate longer or shorter;
  that is a variable, not a constant.
