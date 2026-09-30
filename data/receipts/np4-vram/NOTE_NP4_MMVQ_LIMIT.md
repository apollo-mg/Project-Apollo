# Note -- .73's daily driver fails at 3 concurrent requests because streams x (1 + draft depth) crosses 8, the MMVQ batch limit, not because of the -ts balance

**2026-09-30.** Diagnostic for BACKLOG N16, found during `power-management/NOTE_FAN_CURVE_73.md`. Not pre-registered.
Probes `np_probe.py` (N parallel 256-token generations, VRAM sampled at 200 ms) and `single_probe.py`, raw
`rows.jsonl` and `single.jsonl`.

**Setup:** .73, buun `510cbbbfa`, the daily driver's exact flags (Qwen3.8-27B Q6_K, `-sm tensor`, `-np 4`,
`--kv-unified`, `-c 262144`, VBR auto, MTP `--draft-max 3`, mmproj on GPU), each variant on a fresh server with
`-lv 4`. The wake proxy was stopped during the tests and restarted afterwards on the unchanged unit.

## Concurrent requests (256 tokens each, thinking off)

| config | tokens per decode step at n=3 | n=1 | n=2 | n=3 | n=4 |
|---|---:|---|---|---|---|
| **daily driver** (draft 3) | 12 | 23.9 tok/s | 25.2 total | **all HTTP 500** | **all HTTP 500** |
| draft 2 | 9 | -- | 26.8 total | **all HTTP 500** | -- |
| **draft 1** | 6 | 21.7 | 28.8 total | **33.2 total** | **35.1 total (n=4: 8 tokens)** |
| draft 3, mmproj on CPU (+1.2 GB free on GPU 0) | 12 | 22.3 | 25.5 total | passes, 19.9 total; **+2.25 GB per card** | 20.6 total |

- **The failure point is exactly 8 tokens per step.** Streams x (1 + draft depth) <= 8 always worked (n=2 d3 = 8,
  n=4 d1 = 8); 9 and above failed (n=3 d2 = 9, n=3 d3 = 12), even with 1.9 GB free on GPU 0.
- **8 is `MMVQ_MAX_BATCH_SIZE`** (`ggml-cuda/mmvq.cuh`). Above it, matmuls leave the fused mat-vec kernel for another
  path.
- **Where the memory went:** with the vision projector on the CPU (more headroom), 12 tokens per step passed, but the
  CUDA pool grew **2,256 MiB per card** and aggregate throughput *fell* below one stream (19.9 vs 22.3 tok/s).
- **Consistent with a dequantize-then-cuBLAS path.** I did not trace which buffer. The threshold and the cost are
  measured.

## What -ts would and would not fix

- **The imbalance is real but secondary.** GPU 0 carries the whole vision projector: at load, GPU 0 has 14,375 MiB
  used against GPU 1's 13,239, and with `--no-mmproj-offload` both read 13,175. Evening it with `-ts` gives ~570 MiB
  more headroom on GPU 0. **It cannot fix the failure:** the 12-token path needs about 2.25 GB per card, and the
  draft-2 case failed with 1.9 GB free.
- **VBR `auto` overcommits** (log): it budgets 4,544 MiB per card "from live free device memory at init", before the
  recurrent state (1,197 MiB), the MTP draft context, compute buffers and the projector load. It is "re-derived each
  boundary". Not the cause here: KV use in these tests stayed small.

## Single stream: what draft depth buys (768 tokens, cached second pass)

| prompt | draft 3 | draft 1 | draft 3 gain |
|---|---:|---:|---:|
| prose | 22.77 | 22.50 | +1 % |
| technical explanation | 25.42 | 23.25 | +9 % |
| code | 29.55 | 24.30 | **+22 %** |

Draft 3 also costs ~690 MiB more per card at load than draft 1 (14,375 vs 13,689 MiB on GPU 0).

## Options (Mark's call; the unit is unchanged)

| option | single stream | concurrency | notes |
|---|---|---|---|
| **A: draft 3, `-np 2`** | keeps +11 % mean / +22 % code | 2 at once; a 3rd **queues** instead of failing | recurrent state halves (~600 MiB freed) |
| B: draft 1, `-np 4` | -10 % mean, -18 % code | 4 at once, 35 tok/s total | also frees ~690 MiB/card |
| C: unchanged | best | **3+ at once = HTTP 500 for everyone** | today's state |

Either A or B, plus `-ts` to even the projector's imbalance, removes the failure.
