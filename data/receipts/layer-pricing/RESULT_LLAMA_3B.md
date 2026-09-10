# Both pre-registered predictions FALSIFIED — the cost structure is architecture-specific

**2026-08-26.** `Llama-3.2-3B-Instruct-BF16` on `.73` (2× P100 sm_60), buun `e332b24`.
28 dense KV layers (0–27), no hybrid, no MTP. 112 cells (56 × t8, 56 × t2).
Predictions registered in `PREREG_LLAMA_3B.md` **before** the run.

Null: mean +6.65e-10, SE 9.51e-08, 50% negative — tighter than any prior band.

## Q1 — terminal-layer V: predicted top-3 (conf 0.6). ACTUAL: rank 56/56 and 29/56.

| band | `27v` rank | costliest 6 cells |
|---|---|---|
| fp16→t8 | **56 / 56** — the single CHEAPEST cell | `1k 0k 4k 2k 3k 0v` |
| fp16→t2 | 29 / 56 | `1k 4k 3k 2k 13k 0k` |

The pre-registered abandonment criterion was "`27v` outside the top 10 of 56 in both bands."
**Met, and then some** — at t8 it is dead last of 56.

**The terminal-layer V effect does not cross architecture families.** It is a `qwen35` hybrid
property, where full-attention layers are sparse (every 4th) and interleaved with recurrent
ones. In a dense model the structure is *inverted*: the **early layers' K caches** dominate —
`1k`, `0k`, `4k`, `2k`, `3k` in both bands.

### What this retracts

`RESULT_4B_CONTROL.md` states: *"An allocator does not get a usable per-layer table, but it
should never demote the terminal layer's V cache early."* **That is wrong as a general rule**
and must not be applied to Llama-family models, where the terminal V cache is the *cheapest*
unit in the model and demoting it first is close to optimal.

The finding survives only as: *within `qwen35` hybrids* (27B with MTP, 4B without), the
terminal layer's V cache is the costliest unit. Two models, one family. An allocator that
special-cases "terminal V" globally would demote exactly the wrong units on Llama.

## Q2 — per-cell SNR vs KV layer count: predicted z < 2.0 (conf 0.7). ACTUAL: 37.4 and 18.0.

| model | KV layers | quant | median per-cell z (t8) | `rho_half` |
|---|---:|---|---:|---|
| Qwen3.5-4B | 8 | Q5_K_S | 5.7 | 0.957 PASS |
| Qwen3.8-27B | 16 | UD-IQ4_XS | 2.2 | 0.591 FAIL |
| **Llama-3.2-3B** | **28** | **BF16** | **37.4** | **0.997 PASS** |

Predicted the *lowest* z because it has the *most* KV layers. It has by far the **highest** —
6.6× the 4B and 17× the 27B — and `rho_half` passes at 0.997 / 0.989.

**The 1/n_KV_layers account is dead.** That was already the *second* mechanism proposed for the
4B's advantage (the first, cell count, was falsified by subsampling). Both are now wrong.

### Surviving candidates, none tested

- **Quantization.** Llama is **BF16**; every other band ran a quantized model. Weight quant
  noise may be swamping the KV signal in the others. This is the strongest candidate and the
  one flagged in the prereg as unremoved.
- **Dense vs hybrid.** 28/28 layers carry KV here; the `qwen35` models carry it on every 4th.
- **Family / training.**

**Discriminating test:** the same band on `Qwen3.5-4B-BF16` — already on `.73`
(`/mnt/models/AI_Models/tqstudy/Qwen3.5-4B-BF16.gguf`, 7.8 GB). Same model and layer count as
the Q5_K_S band, differing only in quant. If BF16 lifts per-cell z the way it did for Llama,
quantization is the mechanism and every prior band was measuring partly weight noise.

## Standing

Two registered predictions, both wrong, both wrong in the *direction of assuming generality*.
The pattern is worth naming: each proposed mechanism has been a plausible story fitted to two
data points, and the third point has killed it every time. Nothing here should reach buun as
an allocator rule until the BF16 control separates quantization from architecture.
