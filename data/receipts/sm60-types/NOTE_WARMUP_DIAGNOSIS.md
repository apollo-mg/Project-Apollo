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
