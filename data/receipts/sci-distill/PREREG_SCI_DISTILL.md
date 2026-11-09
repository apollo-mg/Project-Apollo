# Pre-registration -- does a science-reasoning distillation make a model reason better, or only shorter? DeepSeek-V4-Pro-Qwen3.5-9B vs Qwen3.5-9B on GPQA Diamond (thinking on) and M1 (thinking off)

**Registered 2026-11-09, before any row and before either GGUF existed.** Mark approved the test on 11-09. Only procedure
has run: the downloads (sha256 per shard), a template and tokenizer comparison, and runner self-tests on fake servers.

**Why.** Mark's hypothesis (11-09): fine-tunes rarely add anything, but training on science could improve reasoning, and
better reasoning could raise the chance of finding the right way to an answer. Jackrong's DeepSeek-V4-Pro-Qwen3.5-9B
(with Kyle Hessling) is the cleanest candidate: Qwen3.5-9B, about 250,000 math and STEM samples distilled from
DeepSeek-V4-Pro (Max effort), SFT then a light GSPO RL stage, no coding data. Its card reports MMLU-Pro math, physics
and chemistry 90.53 % vs the base's 89.60 % (+0.93 on 1,500 questions, about one standard error) at 8K context, and
36 % fewer tokens per correct answer (median reasoning 676 vs 3,214 tokens). Two things that comparison cannot show: a
long thinker capped at 8K loses answers to the cap, and MMLU-Pro is close to the training data.

**Prior art checked:** `ledger_precheck.py "science reasoning fine-tune GPQA thinking distillation Qwen3.5-9B"` ->
Sage-A1.5, a science fine-tune, recalled no more facts than its base on M1 and refused invented items 0.19 less often
(INDEX L572, `quant-abstention/RESULT_SAGE_MATCHED.md`); Qwopus, a distillation, the same pattern at -0.07 (L590);
thinking on abstains less on AbstentionBench (L573). Nothing on this repo has measured a fine-tune's REASONING against
its base. **What this adds:** the first benefit-side test of a fine-tune here (GPQA Diamond, 198 graduate science
questions written to resist lookup, outside the card's evaluation), with a cap generous enough not to decide the result,
plus the sixth cost-side M1 comparison and the first with an RL stage.

## Files (both converted here, one converter, one recipe)

| arm | source | 
|---|---|
| Q35B (base) | `Qwen/Qwen3.5-9B` @ `c2022362`, BF16, 4 shards. Byte-identical shards to `unsloth/Qwen3.5-9B` (the card's named base): same LFS oids |
| DSV9 (fine-tune) | `Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B` @ `7d7edca1`, BF16, 4 shards |

- Both converted with llama.cpp `67107ac34f` `convert_hf_to_gguf.py --outtype q8_0 --no-mtp` (both checkpoints carry the
  same 775 tensors, MTP head and vision tower included; the head is dropped from both, and neither vision tower is
  converted). Per-tensor type map recorded (expected identical).
- **Tokenizer:** identical vocabulary (248,044) and merges. The fine-tune ships unsloth's tokenizer.json: 7 extra
  audio/TTS special tokens no prompt here uses, and an older pre-tokenizer pattern (`\p{L}+` where Qwen's has
  `[\p{L}\p{M}]+`, i.e. combining marks). Each model keeps its own tokenizer; the token gates below decide.
- **Template:** the fine-tune's differs only in system-message merging; both switch thinking the same way and neither has
  an effort branch.

## Instrument

.194, P100s at 1,063 MHz and 150 W, llama.cpp `67107ac34f` build_sm60, **every server on ONE GPU with identical flags**
(`-ngl 99 -ctk f16 -ctv f16 -fit off --jinja --cache-ram 0`, `GGML_CUDA_ALLREDUCE=internal`), weights from disk.

**M1 (cost side; as every M1 arm):** Q35B on GPU 0 and DSV9 on GPU 2 at the same time, `-c 16384 -np 1`; `run_main.py`,
thinking off, greedy, 1,024 tokens, R-slot on, `--usage`, the stored arms' UNKNOWN ids and render tail (if Qwen3.5's
ids differ from Qwen3.6's, the Q35B server's own become the expectation and DSV9 must match them).

**GPQA Diamond (benefit side):** `run_gpqa.py`. 198 items from the local HF cache. OpenAI simple-evals multiple-choice
prompt; the four choices permuted by a seed from (item, round), identical in both arms; the answer is the LAST
`ANSWER: X` in the content. **Thinking on, Qwen's recommended thinking sampling for both arms** (T 1.0, top_p 0.95,
top_k 20, min_p 0, presence 1.5), per-request seed from (item, round). `max_tokens` 30,000 (`-c 131072 -np 4
--kv-unified`: four slots of 32K; 32 KB of KV per token). Concurrent slots make sampled outputs not bit-reproducible;
that is accepted and recorded.
- **Rounds:** each round asks all 198 items once. Target 4 rounds, minimum 2. Q35B on GPUs 0+1, DSV9 on GPUs 2+3. When
  DSV9 has finished its 4 rounds, its two servers restart serving Q35B (same flags) and join the Q35B arm: a
  progress rule, not an outcome rule. **Stop:** no request starts later than 24 h after the first GPQA request. The
  analysis uses only rounds complete in both arms.
- **Privacy:** GPQA text and answers never enter the repo. Full responses go to `/mnt/TG_2TB/AI/private/sci-distill/`
  (outside the repo); the committed rows hold the item's sha256 prefix, round, correct, answered, finish and token counts.

## Gates (before any row; each failure stops the run)

1. Both GGUFs' sha256 verified on .194; each server serves its own file and its command line carries the flags.
2. **M1 token gate** (`ds41-h2h/prompt_gate.py`, thinking off) and **GPQA token gate** (`gpqa_gate.py`: 792 prompts,
   thinking on, rounds 1-4) print the same hash on both models. *Contingency, registered now:* if either differs, DSV9
   is reconverted with the base's tokenizer files (same vocabulary ids, so the weights map one to one), the gates run
   again, and the difference is reported.
3. Smoke: thinking off returns content and no reasoning; thinking on returns both.

## Analysis

- **M1:** `ds41-h2h/analyze_ds41.py DSV9 Q35B` (bootstrap 10,000, seed 20261103; exact McNemar).
- **GPQA:** `analyze_gpqa.py` (committed and self-tested on synthetic arms before this file): per item, accuracy is the
  mean over the used rounds; primary = paired difference DSV9 - Q35B over items, 95 % bootstrap over items (10,000,
  seed 20261109); a truncated or unanswered request counts as wrong. Registered sensitivity: the same on items never
  truncated in either arm. Reported per arm: truncation and no-answer rates, median completion tokens, tokens per
  correct answer, per-domain accuracy (descriptive).
- **Power:** 198 items at about 4 rounds resolves roughly 5 to 6 points. A null result means "no large effect", not
  "no effect"; if the base is near 80 %, the headroom is small.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **Cost side: the fine-tune pattern holds** | M1 U refused DSV9 - Q35B <= -0.05 | 0.6 |
| P2 | **No general facts added** | M1 H accuracy DSV9 - Q35B <= +0.02 | 0.7 |
| P3 | **Mark's hypothesis: better science reasoning** | GPQA accuracy DSV9 - Q35B >= +0.05, CI lower > 0 | 0.2 |
| P4 | **The card's efficiency transfers** | GPQA median completion tokens DSV9 / Q35B <= 0.7 | 0.8 |
| P5 | **No accuracy cost for the shorter reasoning** | GPQA accuracy DSV9 - Q35B >= -0.03 (point) | 0.6 |

**Named in advance as the most interesting outcome:** equal accuracy at a fraction of the tokens (P4 holds and the CI on
the GPQA difference includes 0 with |point| < 0.03).

## Deviations

Any change to a file, flag, lane, round rule or the analysis after the first M1 or GPQA row gets a numbered Deviation.
