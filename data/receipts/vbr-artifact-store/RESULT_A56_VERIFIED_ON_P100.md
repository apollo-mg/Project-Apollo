# RESULT: buun `a56eeef5` verified on our own hardware — tensor-split prompt caching restored

**Date:** 2026-09-08
**Node:** `.73` — dual Tesla P100 (sm_60, 2×16 GB), CUDA 12.4, Kubuntu
**Build:** `buun-llama-cpp` at `a56eeef51026b09210357526097bd4a2726f6473`, clean tree,
`build_a56`, `CMAKE_CUDA_ARCHITECTURES=60`, Release, `GGML_CUDA=ON`.
Binary self-reports `version: 0.3.0-dev (build 982, commit a56eeef5)`.
**Model:** `Qwen3.5-4B-Q5_K_S.gguf`
**Raw:** `raw/verify_a56_73_20260908.log`

## Why this receipt exists

We reported the tensor-split cache defect on 2026-09-07 (~11:40). Astra was assigned 13:17, buun
landed `a56eeef51 "server: bind tensor-split cache state to physical devices"` at 18:07. Backlog O9
recorded the fix as **NOT YET VERIFIED on our hardware** — the earlier verification receipt
(`RESULT_FIX_VERIFIED_a56eeef5.md`) was taken on the RX 9070 XT. This closes it on the P100 pair,
which is the hardware the original bug was found on.

## Result 1 — prompt cache reuse restored under `-sm tensor`

`cacheab.sh`: the identical ~4,000-token prompt sent twice to a freshly loaded server. A working
cache makes pass 2 reprocess almost nothing.

| arm | pass 1 prompt eval | pass 2 prompt eval | pass 1 wall | pass 2 wall | speedup |
|---|---|---|---|---|---|
| `--split-mode tensor` | 4,010 tok / 4,549.43 ms | **4 tok** / 53.53 ms | 4.762 s | **0.249 s** | **19.1×** |
| `--split-mode layer` | 4,010 tok / 4,789.01 ms | **4 tok** / 53.04 ms | 5.015 s | 0.282 s | 17.8× |

**Tensor split now behaves identically to layer split.** 4,010 → 4 tokens reprocessed in both. Before
the fix, tensor mode reprocessed the entire prefix on every request; layer split was the only mode
that cached, which is why Mark's note — *"Layer splitting is quite a bit slower based on our testing.
Would hate to lose it"* — described a real and unpleasant trade. The trade is gone: you can now take
tensor split's throughput **and** keep prompt caching.

## Result 2 — artifact-store binding restored

`artbind.sh`, five arms. Every arm produced `VBR_ARTIFACT_CAPTURE store ready`:

| arm | config | lanes |
|---|---|---|
| A | `--split-mode tensor` | **2** |
| B | `--split-mode tensor --tensor-split 1,1` | **2** |
| C | `--split-mode layer` | 2 |
| D | `--split-mode layer --tensor-split 1,1` | 2 |
| E | `--split-mode layer`, `CUDA_VISIBLE_DEVICES=0` | 1 (correct — single GPU) |

The original defect reported `runtime_pools=2 bindings=0 lanes=0` under tensor split: the pools
existed but bound to nothing. Both tensor arms now report `lanes=2`. Arm E's `lanes=1` is the
expected single-GPU control, confirming the count tracks real devices rather than being hardcoded.

## Scope and limits

- **K=1 per arm.** This is an existence proof that the fix works, not a rate. Per
  `agent-benchmark-determinism`, that distinction matters on this node.
- Measured on a 4B model at 32k context with `--vbr-floor t4 --vbr-vram 512M`. The mechanism is
  device binding, which is model-independent, but the *magnitude* of the win scales with prompt
  length and will differ on the 27B/40B configs actually used for work.
- Does not re-test the 9070 XT; that is `RESULT_FIX_VERIFIED_a56eeef5.md`.

## Consequence for our own benchmarking

`.73`'s wake-proxy default config runs `-sm tensor`. Every agent benchmark run on that node before
this build was paying full prompt reprocessing on every turn. Any wall-clock comparison that
straddles this build boundary is invalid — see `AFM-26` (server uptime is a variable) and the
`viability/PREREG_TIMEOUT_WALL.md` addendum, where wall-clock timeouts converted throughput loss
into scored INFRA_ERRORs.
