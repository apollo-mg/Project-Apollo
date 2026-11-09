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

## Addendum 1 -- the chain (2026-11-09, before any row)

`run_sci_distill.sh` implements the above with two procedural details. M1 runs Q35B first and DSV9 second, on separate
servers (GPU 0 :8190, GPU 2 :8191), because DSV9's expected UNKNOWN ids and render tail are read from Q35B's header (M1
is greedy at `-np 1`, so order does not change outputs). The thinking-on smoke uses the GPQA sampling, since a greedy
thinking smoke can loop to its cap and fail for a reason that says nothing about the gate. The conversion's size,
sha256 and tensor map are logged by the chain (`raw/chain.log`, `tensor_map.txt`), recorded, not gated.

## Addendum 2 -- M1 with thinking on (registered 2026-11-09, after the thinking-off M1 arms, before any thinking-on row)

**Why.** With thinking off, DSV9 answered 125 of 240 M1 items with a bare "UNKNOWN" (median reply 2 tokens), refusing 0.40
of real hard facts where the base refused 0.03, while its forced answer slot leaned toward UNKNOWN LESS than the base's
(0.53 vs 0.79 on invented items). A model distilled only from thinking traces may have lost its non-thinking mode rather
than its knowledge. Mark asked for the thinking-on run to separate the two (11-09).

**Arms:** Q35BT and DSV9T, M1 as above except `--thinking` and Qwen's thinking sampling (T 1.0, top_p 0.95, top_k 20,
min_p 0, presence 1.5; per-item seed, `--seed-base` default, as Sage's SGTHK1), `--max-tokens 16384`, `--timeout
3600`; the R-slot readout stays thinking-off greedy. One sample per item (K = 1). Same files, build and per-GPU flags
(`-c 20480 -np 1`); each arm runs as four shards (`run_main.py --shard I/4`, new 11-09, default off), one per P100,
Q35BT first, then DSV9T; `merge_shards.py` joins them. Chain: `run_sci_m1think.sh`, which waits for the GPQA chain.

**Analysis:** `analyze_ds41.py DSV9T Q35BT` (both grades), plus per group the share of bare-UNKNOWN replies (the
analyzer's `bare` predicate) and median completion tokens; thinking on vs off within each model is descriptive.

| # | claim | rule | confidence |
|---|---|---|---|
| P6 | **It is the mode, not lost knowledge** | H accuracy DSV9T - Q35BT >= -0.05 (point) | 0.55 |
| P7 | **The bare-UNKNOWN collapse is a non-thinking effect** | DSV9T bare-UNKNOWN share on H <= 0.10 | 0.6 |
| P8 | **The fine-tune pattern under thinking** | U refused, bare UNKNOWN counted, DSV9T - Q35BT <= -0.05 | 0.45 |

## Deviations

Any change to a file, flag, lane, round rule or the analysis after the first M1 or GPQA row gets a numbered Deviation.

**Deviation 1 -- GPQA grading fallback (2026-11-09 14:07, after DSV9's first 3 GPQA rows and before any Q35B GPQA row).**
DSV9 ends its replies with a bare letter ("C") instead of the requested `ANSWER: C` line, so the registered parser
scores them unanswered. I saw this on its first three rows, and I also saw that those three letters matched the gold
answers. The fallback is defined by format alone and applies to both arms identically: when there is no `ANSWER:` line,
the last non-empty content line counts if it is a bare letter A-D, optionally wrapped ("**C**", "(C)", "C.",
`\boxed{C}`). Implemented in `regrade_gpqa.py` (12 test cases, negatives included), which reads the private rows,
reproduces the registered grade exactly, and adds `correct_any` and `answer_form` to text-free files. Generation is
unchanged and nothing is rerun. Both grades are reported: the registered one (`correct`) and the fallback
(`correct_any`, read as the substantive result since it differs from the registered one only in answer format).
The share of bare-letter answers per arm is reported, since format compliance is itself a difference between the models.

**Note on M1 (not a deviation; the instrument's lenient grade already exists):** DSV9 answers 125 of 240 M1 items with
the single word "UNKNOWN" (median reply 2 tokens, vs 53 for Q35B), which the registered strict grade scores NO-ANSWER.
P1 is read on both grades in the result.
