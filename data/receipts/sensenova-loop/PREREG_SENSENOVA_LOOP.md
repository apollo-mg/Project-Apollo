# PREREG: SenseNova-Loop-9B, a looped transformer, on M1 beside Qwen3.5-9B (2026-11-23, before any M1 row)

**Why (Mark, 11-23):** three looped-transformer launches in a month (Inkling-2-Mini, SenseNova-Loop-9B, GLM 5.4 reported).
SenseNova-Loop-9B (SenseTime, 11-17, Apache 2.0) is the small one: 9B dense, 32 physical layers, the middle 24 (4-27)
run twice, so 56 logical layers per token; two-stream hyper-connections; Qwen3.5-style hybrid attention. Unlike Inkling
it can turn thinking off, which our instrument needs. First question: how it does on M1 at its default two loops.
The loop count as a dial is a later test.

**Prior art checked:** `ledger_precheck.py "looped transformer recurrent depth loop count abstention SenseNova"` -> nothing
on looped models. Qwen3.5-9B's own M1 arm exists (`Q35B`, `sci-distill/RESULT_SCI_DISTILL.md`: .194 P100, CUDA build
67107ac34f). **What this adds:** the first looped model on M1, against Qwen3.5-9B re-run on the same build and card.

## Arms (RX 9070 XT; greedy; thinking off; M1 240 items; `quant-abstention/run_main.py --max-tokens 1024 --usage`)

- **SNL:** `SenseNova-Loop-9B-Q8_0.gguf` (official, sensenova/SenseNova-Loop-9B-GGUF, sha256 `0db6188d...`, checked
  after download) on llama.cpp PR #32588 at **`4bc61eed7`**. Not the PR head: the head (`0ba8e4adf`, 11-22) makes each
  full-attention layer's second pass reuse the first pass's KV cache, while the reference implementation
  (`modeling_sensenova_loop.py`, `_VisitCache` keyed by execution index) keeps a separate cache per pass.
- **Q35R:** Qwen3.5-9B Q8_0 (our conversion, sha256 `f904644b...`, the file behind `Q35B`) on the same build.
- **SNLH (exploratory):** SNL's file on the PR head `0ba8e4adf` (shared full-attention caches).
- Server: `-ngl 99 -c 16384 -ctk f16 -ctv f16 -np 1 --jinja --cache-ram 0`, fresh server per arm, mmproj not loaded,
  no MTP. Thinking off as every M1 arm (the runner's closed-think render check on).

## Gates (before any M1 row is read)

- **G1 load:** the server log reports architecture sensenova_loop, loop count 2 and 57 blocks.
- **G2 sanity (perplexity):** SNL and Q35R share a tokenizer (qwen35 pre-tokenizer, 248,320 tokens), so their
  perplexity on the same text is comparable. `llama-perplexity` on wikitext-2 test, `-c 512`, first 100 chunks, both on
  the SNL build. If SNL's perplexity exceeds 1.5x Q35R's, the implementation is treated as broken: no M1 claim.
- Reported, not a gate: Q35R against the stored Q35B rows (different backend and build, so agreement need not be exact).

## Measures and predictions

Grading: the run_main grader with the bare-answer rule (`idk-lora/bare_rule.py`, as `idk-lora` and `frozen-layers`).
Primary: invented items declined (of 100); hard-question accuracy, wrong and declined (of 100); easy accuracy (of 40).
Paired differences SNL - Q35R with a bootstrap over items, 10,000 resamples, seed 20261123.

- **H1:** SNL declines fewer invented questions than Q35R (difference < 0). Basis: heavy agent post-training, and five
  of the seven post-trained variants in our series cut "I don't know"; lineage and recipe not stated. Confidence 0.55.
- **H2:** looping buys compute, not stored facts: SNL's hard accuracy is at most Q35R's + 0.05. Confidence 0.6.
- **E1 (exploratory):** the head build's shared caches change at least 24 of the 240 answers (10 %). Confidence 0.6.
- Reported without prediction: unfinished answers, output tokens and decode speed per arm.

## Limits stated now

Full-model numerical parity with the reference is unverified (the PR says so); G2 catches gross breakage only. Lineage
not stated, so SNL vs Q35R is a comparison of two models, not a fine-tune against its base. One condition (thinking off,
greedy, two loops), one quant (the official Q8_0).
