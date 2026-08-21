# Pre-registration — 2-GPU vs 4-GPU tensor split on `.194`

**2026-08-21, written before any arm ran.**

## Question

Does one 4-GPU job beat two concurrent 2-GPU jobs on **total throughput**? That decides how every
future sweep is scheduled: if 4-GPU is not meaningfully faster than 2-GPU, then whenever a model
fits in two cards **with the needed context**, running two experiments simultaneously is strictly
better.

## Stack

`.194`, 4× Tesla P100-PCIE-16GB (sm_60), **1063 MHz / 150 W pinned on all four** (verified at
launch). `~/llama_stock/build_puzzle/bin/llama-bench`, tree `73a55486c`, **binary built
2026-07-12 04:35:34, commit 04:30:03 — 5m31s after, so the sm_60 FAST_FP16 carve-out is in**.
`Qwen3.8-27B-Q6_K` (22.88 GB, dense), `-ngl 99`, `-p 512 -n 128`, `GGML_CUDA_ALLREDUCE=internal`
pinned (NCCL is broken on these P100s and `-sm tensor` defaults to it on Linux).

NUMA: GPU0+GPU1 → node 0, GPU2+GPU3 → node 1, `PHB` within a pair, `SYS` (PCIe + QPI) across.
Same-socket arms are pinned with `numactl --cpunodebind=N --membind=N`; the 4-GPU arm spans both
and cannot be.

## Arms

| id | config | purpose |
|---|---|---|
| `L2` | `-sm layer`, GPUs 0,1 | anchor against this morning's 7.7 t/s server figure |
| `T2a` | `-sm tensor`, GPUs 0,1 | the standard pairing |
| `T2b` | `-sm tensor`, GPUs 2,3 | socket symmetry — are the two halves equivalent? |
| `T4` | `-sm tensor`, GPUs 0,1,2,3 | the pooled case, crosses QPI |
| `CONC` | `T2a` **and** `T2b` simultaneously | **the decision arm** |

## Predictions

| # | prediction | conf |
|---|---|---|
| **E1** | `L2` ≈ 7.7 t/s, within 15 % of the server measurement | 0.70 |
| **E2** | `T2a` ≈ 1.6× `L2` (~12–13 t/s), matching `.73`'s measured 1.628× on a different quant | 0.70 |
| **E3** | `T4` > `T2a`, but **less than 2×** it — all-reduce now crosses QPI | 0.75 |
| **E4** | `T2b` within 5 % of `T2a` — the sockets are symmetric | 0.85 |
| **E5** | Under `CONC`, each job stays within 10 % of its solo speed | 0.60 |
| **E6** | **`CONC` aggregate > `T4`** — i.e. two 2-GPU jobs beat one 4-GPU job on total work | **0.70** |

**E6 is the decision.** If it holds, sweeps get scheduled as paired 2-GPU arms whenever the model
fits. If it fails, pooling wins and the concurrency idea is dropped.

## Falsification notes written in advance

- **`T4` scaling near 2× would falsify the QPI concern entirely** and make pooling the default.
  That is a live possibility: under tensor split each GPU reads only its shard, so aggregate
  bandwidth genuinely quadruples; the question is only whether all-reduce over `SYS` eats it.
- **A `CONC` slowdown would not necessarily be QPI.** Both jobs share host RAM bandwidth, the
  PCIe root complexes and the disk. If `CONC` degrades, the cause needs isolating before it is
  attributed to the interconnect.
- `llama-bench` reports **decode (`tg`) and prefill (`pp`) separately**. Prior work found split
  mode helps them in *opposite* directions — prefill favoured layer split. Both get reported;
  only `tg` bears on sweep scheduling, since fixture items are generation-bound.
- One model, one quant, one context. `AFM-24`: this bounds the claim to Q6_K-sized dense models.
