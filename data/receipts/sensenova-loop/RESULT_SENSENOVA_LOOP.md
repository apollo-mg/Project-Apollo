# RESULT (stopped at the sanity gate): SenseNova-Loop-9B on llama.cpp PR #32588 has 2.07x Qwen3.5-9B's wikitext perplexity (16.56 vs 8.02), over the registered 1.5x limit, so no M1 arm was run; diagnostics point to the training mix rather than a broken port, but parity with the reference is unproven

**Prereg:** `PREREG_SENSENOVA_LOOP.md` (`61d9e4bd`) and Deviation 1 (`8f8d25ec`, G1 rewritten before any perplexity or M1
row). **Run:** 2026-11-23 17:10-17:12 EST, RX 9070 XT, PR #32588 at `4bc61eed7` (`run_snl.sh`); the official Q8_0
(sha256 `0db6188d...`, matched Hugging Face's). **Records:** `raw/state.log`, `raw/ppl_*.log`; the failed first launch
in `raw/g1_failed/`; diagnostics in `raw/diag/`.

## Gates

- **G1 load (as Deviation 1): passed.** Header `sensenova_loop`, 2 loops, 57 blocks; "model loaded"; the only unused
  tensors are `blk.56` (the MTP layer).
- **G2 perplexity: failed.** wikitext-2 test, `-c 512`, 100 chunks, same build: SNL **16.56** (+/- 0.36), Qwen3.5-9B
  **8.02** (+/- 0.13): 2.07x against the 1.5x limit. Per the prereg, no M1 claim; the run stopped before any M1 row.

## Diagnostics after the gate (exploratory; they do not reopen it)

| check | result | reading |
|---|---|---|
| the official file's routing weights | `hc_*` weights and biases F32 | not a quantisation loss |
| CPU instead of GPU, same build, 20 chunks | 17.49 vs GPU 17.54 | not a ROCm backend bug |
| source code (llama.cpp C++, 60 chunks) | SNL 2.69 vs Qwen3.5-9B 2.29 (1.18x) | the gap is mostly on Wikipedia text: a training-mix difference fits better than a uniform breakage |
| five easy chat questions, greedy, thinking off | all right: Canberra, Austen, 391, a correct French translation, a correct Fibonacci function | the port works at least roughly |
| PR head `0ba8e4adf` (second loop reuses the first loop's full-attention cache) | 16.96 vs 16.56 | the shortcut costs a little (+2.4 %) |

A tester on the PR reported the model assuming Chinese input, consistent with a Chinese-heavy mix that would raise
English Wikipedia perplexity. None of this proves numerical parity with SenseTime's reference implementation, which the
PR itself lists as unverified.

## What would settle it

The reference implementation's perplexity on the same chunks (BF16 safetensors, 19.4 GB, and SenseTime's
`modeling_sensenova_loop.py`, run after reading it). If it is also about 16.5, the port is faithful and M1 can run under
an amendment that replaces G2 with agreement with the reference.
