# Plan (not a prereg yet) — is GGUF quantization damage concentrated on hesitation tokens?

**Written 2026-09-23, before any measurement.** Source: Lotfi et al.,
https://sanaelotfi.github.io/blog/quantized-reasoning-models/ (shared by buun).

## Their claim
On R1-distills and QwQ-32B under GPTQ/AWQ/FlatQuant, per-token KL vs full precision is ~100x higher on
hesitation markers ("Wait", "But", "Alternatively") at high-entropy positions than on math tokens;
this drives overthinking (3-bit AWQ MATH-500: 85.6% -> 47.0%, CoT 5.2K -> 23.4K tokens; up to 52% of
failures reach the right answer then abandon it). A flat logit penalty on ~50 markers cut CoT 12-23%
with accuracy held.

## Our step 1 (cheap, no new model runs beyond KLD passes)
Class-conditional KLD on our existing Qwen3.8-27B GGUF quant ladder (IQ2..Q6 vs Q8/BF16 reference):
`llama-perplexity --kl-divergence` per-token output, then split positions by the NEXT token class
(hesitation markers vs everything else), and by reference-model entropy. Their mechanism predicts
hesitation-position KLD separates the quants far more than mean KLD does. Untested on k-quants/imatrix.

## Step 2 (only if step 1 shows the concentration)
`--logit-bias` penalty on the marker set, on the CAL unanswerable items where we saw NO-STOPs, at
xhigh (medium thinks too briefly to show it). Intervention test, NOT a recommended config (vendor
sampling rule). Pairs with NOTE_OVERTHINK_DETECTOR and the blocked PREREG_OVERTHINK_INJECTION.

## Before writing the prereg
- ledger_precheck.py "KL divergence per token hesitation overthinking quantization" --deep
- find which Qwen3.8 ladder GGUFs + reference are still on disk (.194 ~/AI/Models/ladder, NAS)
- check how the existing KLD receipts dumped per-token data (battle16gb, kld/)
