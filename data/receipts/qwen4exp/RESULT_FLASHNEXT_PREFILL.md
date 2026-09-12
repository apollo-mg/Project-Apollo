# Flash-Next prefill is ~35 tok/s and flat — pp/tg is 3-4x where healthy hardware is 10-100x

**2026-09-03.** `.194`, 2x P100 sm_60 @ 150 W / 1063 MHz. Build `build_sm60_qwen4` (`7a918624b`).
Model `Qwen3.8-Flash-Next-UD-Q2_K_XL`, `-c 16384 -ngl 99 -fa on --jinja -np 1 -fit off -ncmoe 30
-sm tensor --kv-unified`, `GGML_CUDA_ALLREDUCE=internal`. `cache_prompt:false`, `n_predict 16`,
warm-up discarded.

Prompted by buun asking directly: *"what's the prefill like on that / if you're getting 12 tok/s tg
I can only imagine the pp."*

## Result

| prompt tokens | prefill tok/s | prefill wall |
|---|---|---|
| 488 | 37.69 | 12.9 s |
| 1,817 | 35.01 | 51.9 s |
| 3,645 | 35.38 | 103.0 s |

Decode on the same legs: 8.15–8.41 tok/s.

**pp/tg ≈ 3–4x.** Healthy hardware runs 10–100x, because prefill is batched and compute-bound
while decode is memory-bound. Here prefill is barely faster than generation.

**It is flat, not degrading.** 37.7 -> 35.0 -> 35.4 across a 7x prompt-size range. That is the
signature of a saturated resource, not of an algorithm scaling badly.

Extrapolated: a full 16,384-token context costs **~7.7 minutes before the first token**.

## Mechanism

Consistent with the host-expert-fetch bottleneck. Decoding one token routes to ~10 of 512 experts,
so consecutive tokens amortise some fetches. Prefilling ~1,800 tokens at once touches
**essentially every expert**, so the entire offloaded weight set streams from host RAM with nothing
to amortise against. Same mechanism as [RESULT_BATCH_PARALLELISM.md](RESULT_BATCH_PARALLELISM.md),
at maximum severity.

**Independent corroboration:** buun reports **~40 tok/s** decode on the same model with a single
3090 + DDR5. He is also offloading experts (24 GB cannot hold this model). The difference is host
memory bandwidth: DDR5 versus DDR4-2133 running **half channels** (4 of 16 DIMM slots populated =
2 of 4 channels per socket). That predicts roughly 3-5x, and 40/12 = 3.3x. The ceiling is host
bandwidth, not the GPUs.

## Caveats

- **This config no longer exists.** `-sm tensor` on `qwen4exp` was deny-listed by upstream PR
  #27941 and is refused by current buun and upstream. Numbers stand as a record of this binary;
  a rerun needs `-sm layer`. See [RESULT_META_BACKEND_SEGFAULT.md](RESULT_META_BACKEND_SEGFAULT.md).
  **Update 2026-09-12:** buun's fork re-admitted `qwen4exp` for `-sm tensor` on 2026-09-10
  (`9edf91e99`, *"retain Qwen4 tensor-split admission after master sync"* — the inherited upstream
  denylist had been blocking full-model loads and silently skipping the test). Upstream still denies
  it. On his fork a rerun can use tensor split again; whether the meta-backend segfault is also fixed
  is untested.
- Sweep died at the 4th point: the server segfaulted, which is how the meta-backend bug was found.
  Points 1-2 are from `timings` JSON; point 3 is from the server log immediately before the crash.
- K=1 per size. No repeats.
