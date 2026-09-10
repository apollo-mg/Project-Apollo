# Pre-registration — Llama-3.2-3B band, written BEFORE the run

**2026-08-26.** `Llama-3.2-3B-Instruct-BF16` on `.73` (2× P100 sm_60), buun `e332b24`.
28 KV layers (0–27), **dense standard attention** — no SSM hybrid, no MTP head.
Bands: fp16→t8 and fp16→t2, 56 cells each = 112 cells.

Two independent questions, both falsifiable.

## Q1 — does the terminal-layer V effect cross architecture families?

So far it holds only within `qwen35` hybrids: `63v` rank 1 in all three Qwen3.8-27B bands,
`31v` rank 1/1/2 in the Qwen3.5-4B bands. Llama-3.2 is a different family with ordinary dense
attention at every layer.

**Prediction: `27v` lands in the top 3 of 56 cells in both bands. Confidence 0.6.**

Deliberately not higher — every replication so far shares the `qwen35` hybrid layout, where
full-attention layers are sparse (every 4th) and interleaved with recurrent ones. The terminal
attention layer may be special *because* of that interleaving, in which case a dense model has
no reason to show it. A miss here is informative, not a failure.

## Q2 — does per-cell SNR track KV layer count?

The cell-count explanation for the 4B's `rho_half` pass was **falsified** by subsampling.
The surviving account is per-cell signal-to-noise, driven by what fraction of the KV cache
one layer represents:

| model | KV layers | median per-cell z (t8) |
|---|---:|---:|
| Qwen3.5-4B | 8 | 5.7 |
| Qwen3.8-27B | 16 | 2.2 |
| **Llama-3.2-3B** | **28** | **predicted < 2.0** |

**Prediction: median per-cell z at t8 is below 2.0, and `rho_half` FAILS the 0.90 gate,
worse than the 27B's 0.591. Confidence 0.7.**

If instead the 3B shows high per-cell z despite 28 layers, the 1/n_layers account is wrong and
the 4B's advantage is something else — model size, quant (Q5_K_S vs BF16 vs UD-IQ4_XS), or
split mode. That is the main confound this run does NOT remove.

## What would make me abandon the terminal-V claim

`27v` outside the top 10 of 56 in both bands. That would confine the finding to `qwen35`
hybrids and it should be reported to buun as such before he acts on it.
