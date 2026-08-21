# Two 2-GPU jobs beat one 4-GPU job by 1.70×, with zero contention

**2026-08-21**, `.194`, 4× Tesla P100-PCIE-16GB (sm_60), **1063 MHz / 150 W pinned, verified
before and after**; end temps 45–54 °C, no clock drift. `llama-bench` from
`~/llama_stock/build_puzzle` (tree `73a55486c`, **binary built 5m31s after the sm_60 FAST_FP16
carve-out commit**). `Qwen3.8-27B-Q6_K`, 21.30 GiB / 27.32 B params, dense, `-ngl 99 -p 512
-n 128 -r 3`, `GGML_CUDA_ALLREDUCE=internal`. Same-socket arms NUMA-pinned. Raw
`raw_bench_2v4.log`. Pre-registration: `PREREG_2V4.md`.

## Result

| arm | GPUs | split | pp512 | **tg128** |
|---|---|---|---:|---:|
| `L2` | 0,1 | layer | 106.39 ± 0.05 | **7.70 ± 0.00** |
| `T2a` | 0,1 | tensor | 173.46 ± 0.07 | **13.00 ± 0.02** |
| `T2b` | 2,3 | tensor | 172.79 ± 0.01 | **13.00 ± 0.03** |
| `T4` | 0,1,2,3 | tensor | 224.10 ± 0.44 | **15.34 ± 0.05** |
| `CONC` A | 0,1 | tensor | 173.48 ± 0.01 | **13.00 ± 0.03** |
| `CONC` B | 2,3 | tensor | 173.70 ± 0.04 | **13.03 ± 0.03** |

## The decision

**`CONC` aggregate 26.03 t/s vs `T4` 15.34 t/s — 1.70× more total work.**

And the two concurrent jobs cost each other **nothing**: 13.00 solo → 13.00 concurrent, 13.00 →
13.03. Not "within noise" — *identical to the third digit*, on a box where both jobs share host
memory, both PCIe root complexes and the disk.

**Operational rule: whenever a model fits in two cards with the context the test needs, run two
experiments simultaneously.** There is no throughput reason to ever pool all four for a model
this size.

## Why 4 GPUs buys so little

| step | factor |
|---|---:|
| layer → tensor, 2 GPUs (`L2`→`T2a`) | **1.688×** |
| 2 GPUs → 4 GPUs, tensor (`T2a`→`T4`) | **1.180×** |

Doubling the GPU count bought **18 %**. For comparison, `.73` measured **1.628×** for the same
layer→tensor step on a different quant (`RESULT_P100_SM_TENSOR.md`) — so the 1→2 scaling
reproduces across nodes and quants, and the 2→4 step is where it collapses.

Prefill degrades less than decode: 1.63× then 1.29×. Consistent with all-reduce cost being
amortised over a 512-token batch during prefill but paid per token during generation.

**What this does NOT establish:** that QPI is the cause. The 2→4 step changes **two** things at
once — it crosses the socket boundary *and* doubles the number of all-reduce participants. This
box has only two GPUs per socket, so a 4-GPU same-socket control **cannot be built here**, and
`AFM-20` applies: a ladder that varies one axis over a fixed everything-else is n=1 on
everything else. The measured fact is that 2→4 scales at 1.18×; the attribution is open.

## Corroborates a recollection

Mark recalled ~25 t/s on this model with tensor split plus speculation. `T4` at **15.34 t/s**
without speculation, times the Q6_K MTP multiplier of **1.82–1.84×** measured in
`RESULT_SPLIT_X_MTP.md`, gives **27.9–28.2 t/s** — and `T2a` × the same multiplier gives
**23.7 t/s**. Either configuration lands on ~25. The recollection was sound; what was missing
was the un-speculated baseline, which is now measured.

## Prediction scorecard

| # | prediction | conf | outcome |
|---|---|---|---|
| E1 | `L2` ≈ 7.7 t/s, within 15 % of the server figure | 0.70 | **correct — 7.70, exact.** Two independent measurement paths (llama-bench vs server+client timing) agree to three digits |
| E2 | `T2a` ≈ 1.6× `L2` | 0.70 | correct — 1.688× |
| E3 | `T4` > `T2a` but < 2× | 0.75 | correct — 1.180×, far below the ceiling |
| E4 | `T2b` within 5 % of `T2a` | 0.85 | correct — identical; the sockets are symmetric |
| E5 | `CONC` each within 10 % of solo | 0.60 | **correct, and understated** — 0 % degradation |
| E6 | `CONC` aggregate > `T4` | 0.70 | **correct — 1.70×** |

**6 of 6.** Worth noting against the day's record: the two calls that were *wrong* earlier
(`NO-STOP` as a model property, tensor split as a "trap") were both reasoned from a mental model
of the system. These six were predictions about a measurement whose mechanism was already
receipted. `AFM-17` again — source-structure reasoning is where this project's predictions fail,
and measured-mechanism extrapolation is where they hold.

## Scope

One model, one quant, one context, `-np 1`, dense. Nothing here predicts MoE, where expert
routing interacts with tensor split, or batched serving, where the single-stream case most
favourable to tensor split no longer applies.
