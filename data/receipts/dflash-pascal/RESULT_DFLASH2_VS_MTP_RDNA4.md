# MTP beats DFlash-2 on a 16 GiB card — and DFlash-2 cannot run at its design depth at all

**2026-09-03.** RX 9070 XT (gfx1201), buun-llama-cpp `3823c9eb6`.
Target `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (3.05 bpw, 9.69 GiB, MTP head inline blk.64 Q6_K).
Drafter `incoai/Qwen3.8-27B-DFlash2-GGUF` **Q4_K_M (1.09 GiB)**.
`-c 8192`, f16 KV, `-fa on --jinja --kv-unified -np 1`, temp 0, seed 42, 3 prompts x K=3.
Pre-registered in `PREDICTION_DFLASH2_VS_MTP_RDNA4.md`. Raw: `raw_dflash_depth.jsonl` / `.log`.

## Result

| arm | median decode | vs none | VRAM | draft acceptance | mean accepted len |
|---|---:|---:|---:|---:|---:|
| no spec | 30.25 t/s | 1.00x | 76% | — | — |
| **MTP** | **50.85 t/s** | **1.68x** | **82%** | **0.615** | 2.23 |
| DFlash-2, `--draft-max 2` | 44.50 t/s | 1.47x | 86% | 0.573 | 2.15 |
| DFlash-2, `--draft-max 4` | 37.33 t/s | 1.23x | 87% | 0.390 | 2.56 |
| DFlash-2, `--draft-max 6` | 33.64 t/s | 1.11x | 89% | 0.266 | 2.59 |

**MTP wins on every axis simultaneously**: faster (50.85 vs 44.50 best DFlash), cheaper
(82% vs 86-89% VRAM), and higher acceptance (0.615 vs 0.573). There is no operating point
where DFlash-2 is preferable here.

DFlash-2 gets *worse* with depth. Acceptance collapses 0.573 -> 0.266 while mean accepted
length barely moves (2.15 -> 2.59): the extra draft tokens are almost all rejected, so deeper
drafting buys 0.44 tokens per cycle at the cost of 3x the wasted draft compute.

## The blocker that shaped the whole test

The auto-preselected driver reports `adaptive shared DFlash2 driver (block_size=13,
draft-max=12)` and then demands a **fixed 7,780.50 MiB allocation**:

```
E ggml_backend_cuda_buffer_type_alloc_buffer: allocating 7780.50 MiB on device 0:
  cudaMalloc failed: out of memory
```

**That figure is invariant to context** — byte-identical at `-c 4096`, `-c 2048` and
`-c 1024`. It is not KV. With a 9.69 GiB target that needs ~17.3 GiB, so **DFlash-2 does not
load at its default depth on a 16 GiB card at any context length.** Capping `--draft-max`
makes it fit; every DFlash row above is therefore running below its design point
(`dflash.block_size = 8` in the GGUF, driver preselecting 13).

Worth passing to buun: the model file declares `block_size = 8`, the driver preselects
`block_size=13, draft-max=12`, and nothing reconciles them or degrades gracefully — it OOMs
and exits rather than backing the depth off to fit.

## Published acceptance figures do not reproduce

`incoai`/`z-lab` report acceptance length **5.28 (BF16) / 5.13 (Q8_0) / 5.39 (Q4_K_M)**.
Measured here: **2.15 - 2.59**, less than half, at every depth that fits. Either the metric
differs (their "acceptance length" may count completion tokens per verification step under a
different definition), or the design depth we cannot reach is where those numbers live.
**Not claimed as a contradiction** — stated as an unexplained gap, with our definition made
explicit: `mean len` is llama.cpp's own `draft acceptance = accepted/generated, mean len`.

## Prediction scoring

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | both spec modes beat no-spec | 0.90 | **HIT** — every arm > 30.25 |
| P2 | DFlash-2 beats MTP on raw decode | 0.60 | **FALSIFIED** — MTP 50.85 vs 44.50 |
| P3 | margin smaller than the 9B's +34% | 0.55 | **HIT**, and then some — the sign flipped |
| P4 | DFlash-2 does not fit at `-c 32768` | 0.85 | **HIT**, and understated — it fits at *no* context at default depth |
| P5 | both fit at `-c 8192` | 0.75 | **PARTIAL** — only with `--draft-max` capped |
| P6 | MTP wins per GiB spent | 0.80 | **HIT**, decisively |

## Against our own DFlash-1 numbers on the same card

`RESULT_S2_DFLASH_PASCAL.md` carries the RX 9070 XT columns from the earlier drafter
showdown — **Qwen3.5-9B-Q8_0 target, DFlash-1 drafter (1.3 GB Q8_0)**:

| draft depth | MTP | DFlash-1 | winner |
|---|---:|---:|---|
| off | 55.27 | 55.27 | — |
| n=3 | 107.95 (1.95x) | **116.68 (2.11x)** | DFlash +8% |
| n=7 | 104.53 (1.89x) | **140.03 (2.53x)** | DFlash +34% |
| n=15 | 76.35 (1.38x) | **150.66 (2.73x)** | DFlash +97% |

Today, **Qwen3.8-27B-IQ3_XXS target, DFlash-2 drafter (1.09 GiB Q4_K_M)**:

| draft depth | MTP | DFlash-2 | winner |
|---|---:|---:|---|
| off | 30.25 | 30.25 | — |
| shallow (inline / d2) | **50.85 (1.68x)** | 44.50 (1.47x) | MTP +14% |
| d4 | — | 37.33 (1.23x) | MTP +36% |
| d6 | — | 33.64 (1.11x) | MTP +51% |
| d12 (design depth) | — | **will not load** | — |

**The result inverts, and the mechanism is legible.** DFlash-1 did not beat MTP by being
better at shallow depth — at n=3 it was only +8%. It won by *scaling*: its advantage grew
monotonically to n=15, where MTP had already collapsed below its own n=3 figure. **DFlash's
entire edge is depth**, and depth is exactly what a 27B target on a 16 GiB card cannot buy.
Capped at d6, we are measuring DFlash in the regime where it was never ahead.

Not an apples-to-apples inversion, and it should not be quoted as one — target changed (9B
Q8_0 -> 27B IQ3_XXS), drafter generation changed (1 -> 2), and the absolute floor halved
(55.27 -> 30.25 t/s) because the target is 3x the parameters. What transfers is the *shape*:
DFlash needs depth, MTP does not, and headroom decides which one you can have.

## We predicted this on 2026-08-20, before there was a llama.cpp path

`BACKLOG.md` item **S5**, written when the DFlash2 weights first hit disk:

> "Our `S2` result already shows DFlash's depth advantage *inverts* on Pascal and that
> `dfl_n15` **OOMs at 16 GB** because DFlash carries a separate model + context where MTP
> shares the target's; **top-16 candidates per position can only make that worse**, and no
> memory requirements are documented."

That is exactly what happened: a fixed 7,780.50 MiB allocation, undocumented, that blocks the
design depth outright. The same entry flagged the blog's claim of **2.7-3.4x on
Qwen3.8-27B at batch 1** and noted it was validated only on "M5 Max, Blackwell and TPUs —
all memory-rich and modern." **Measured here on a memory-poor card: 1.47x.** The gap is not
mysterious; it is the prediction.

S5 also flagged `num_target_layers: 64` against the 27B's 65 blocks as needing reconciliation
before porting. Unresolved, and now joined by a second mismatch: the GGUF declares
`block_size = 8` while the driver preselects `block_size = 13`.

## Two errors of mine, recorded

1. **I diagnosed our local drafter as "stale, wrong arch, off-by-one layer ids".** It was
   not. The published `incoai` GGUFs carry *identical* metadata — arch `dflash`,
   `block_size 8`, `dflash.target_layers = [6,20,34,48,62]`, 81 tensors. Our Aug-23 file was
   correct all along.
2. **I attributed the first failure to the file.** The
   `check_tensor_dims: tensor 'blk.0.ssm_g.weight' not found` error is **flag-dependent, not
   file-dependent** — the same BF16 file under different flags OOMs instead. What triggers
   the `ssm_g` path specifically is still unidentified and is the one loose thread here.

## Bottom line for a 16 GiB card

Use MTP. It is inline in the `-mtp` GGUFs (zero extra weights), gives 1.68x, costs 6
percentage points of VRAM, and beats every DFlash-2 configuration that fits. DFlash-2 wants
headroom this card does not have; on a 24 GiB+ card at its design depth the answer could
easily invert, and this receipt says nothing about that case.
