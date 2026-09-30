# Note -- why the first requests after a fresh server run slow on .194: warm-up, or page faults on the mmapped embedding table?

**Written 2026-09-29 ~20:35, before the diagnostic ran.** A post-hoc diagnostic, not a registered experiment.

`RESULT_SM60_TYPES.md` and `RESULT_HC_Q8.md` saw each fresh server's first ~6 decode requests run 5-10 % slow and
noisy, then flat. The two receipts first explained this as a warm-up transient (and a memory rule said "discard ~6").
A second mechanism fits the same data:
- Flash-Next's 28.8 GB `per_layer_token_embd` is host-resident and mmapped (`CPU_Mapped model buffer size = 27465.95 MiB`);
- every generated token looks up its row there;
- rep 2 repeats rep 1's prompts at temp 0, so it generates the same tokens, whose rows are already in page cache.

**What each explanation predicts:**

| | warm-up | page faults |
|---|---|---|
| llama-server major faults during rep 1 | flat | climbing |
| llama-server major faults during rep 2 (same prompts) | flat | ~flat |
| 6 novel prompts after rep 2 | settled speed | slow again, faults climb |
| rep 1 after pre-reading the embedding shard into page cache | still slow | settled speed |

**Procedure:**
1. UD-Q2_K_XL, the kernel run's flags.
2. `sync; echo 3 > drop_caches`, then a fresh server and one discarded warm-up.
3. Rep 1 and rep 2 of the 6 speed prompts, then 6 novel prompts, reading `/proc/PID/stat` field 12 (majflt)
   before and after each request.
4. Leg 2: a fresh server, then `cat` of the embedding shard to `/dev/null` (page cache warm), then rep 1 again.

## Result (ran 20:40-21:00): page faults, not warm-up

Raw: `raw_hc/warmup_diag.jsonl`. UD-Q2_K_XL at 1063 MHz, llama-server major faults per request (`/proc/PID/stat`).

| leg | requests | tok/s | major faults per request |
|---|---|---:|---:|
| cold cache, rep 1 (6 fixed prompts) | 6 | 18.52-19.75 | **1,583-6,483** |
| cold cache, rep 2 (same prompts) | 6 | **21.04-21.11** | **0** |
| cold cache, 6 novel prompts | 6 | 18.81-19.68 | **3,089-5,488** |
| embedding shard pre-read (`cat`, 62 s), rep 1 | 6 | **20.98-21.06** | 0-8 |
| pre-read, 6 novel prompts | 6 | **21.00-21.07** | 0 |

Every row of the page-fault column in the prediction table came true.

- **The "slow first requests" were first-touch page faults** on the mmapped 28.8 GB `per_layer_token_embd` (shard 2
  of 3), read from .194's SATA SSD. The first time any token id appears, its row is read from disk.
- **Warm-up plays no part.** Novel text on a long-running server is just as slow until its tokens have been seen.
  The ~10 % decode loss is real for any text whose tokens are not yet in page cache.
- **The bracketing GSQB run that "never settled"** had a different model generating different tokens after heavy
  page-cache churn from the rewrite, so its rows were cold.
- **The fix is operational:** pre-read the embedding shard once after start (`cat shard > /dev/null`, 62 s; it fits
  in .194's 128 GB), or load with `-lm mmap+mlock`. Decode then runs at the cached rate from the first request.

**Corrections this forces:**
- `RESULT_SM60_TYPES.md` / `RESULT_HC_Q8.md`: "warm-up transient, ~6 requests" becomes page faults, and "settled"
  becomes "table rows cached". The kernel-run medians (24 rows each) were dominated by cached requests, so T4 and T5
  stand.
- `viability/RESULT_SWIFT_FLASHNEXT.md`: the no-MTP speed medians mixed faulted and cached requests. See the
  correction there.
