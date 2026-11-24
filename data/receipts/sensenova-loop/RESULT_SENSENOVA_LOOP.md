# RESULT: SenseNova-Loop-9B, a looped model whose card puts it level with Qwen3.8-27B on agent benchmarks, knows a third as many hard facts as Qwen3.5-9B (14 vs 42 of 100) and declines fewer invented questions (53 vs 65); the llama.cpp port matches SenseTime's reference, and the PR's newest commit changes 209 of 240 answers

**Prereg:** `PREREG_SENSENOVA_LOOP.md` (`61d9e4bd`), Deviation 1 (`8f8d25ec`, G1 rewritten before any perplexity or M1
row), Amendment 1 (`6bc85aa2`, the reference check, before any reference number). **Runs:** 2026-11-23, RX 9070 XT,
llama.cpp PR #32588 at `4bc61eed7` (SNL, Q35R) and the PR head `0ba8e4adf` (SNLH), the official Q8_0 (sha256
`0db6188d...`); the reference on .194's CPUs. **Analysis:** `analyze_snl.py` -> `summary.txt`, `RESULT_snl.json`;
`amend1_verdict.py`. **Records:** M1 rows in `quant-abstention/raw/main_{SNL,Q35R,SNLH}.jsonl`; gates, the reference and
diagnostics in `raw/` (`g1_failed/`, `g2_stop/`, `reference/`, `diag/`).

## How it got here

1. **G1 (load)** passed as rewritten in Deviation 1 (header `sensenova_loop`, 2 loops, 57 blocks; only `blk.56`, the MTP
   layer, unused).
2. **G2 (perplexity) failed:** wikitext-2, `-c 512`, 100 chunks: SNL 16.56 against Qwen3.5-9B 8.02 (2.07x > 1.5x). The
   run stopped before any M1 row. Diagnostics (`raw/diag/`): CPU = GPU (17.49 vs 17.54 at 20 chunks); on source code
   the gap is 1.18x; five easy chat answers right; router weights F32 in the file.
3. **Amendment 1, the reference:** SenseTime's `modeling_sensenova_loop.py` (read in full first; byte-identical to the
   copy read) on the full-precision weights (all LFS hashes checked twice), FP32 on CPU, transformers 5.18.0, torch
   2.15.0, the same tokens (identical on all 297,193; `raw/diag/tokenizer_check.txt`), scored as `llama-perplexity`
   does: **17.5599 against llama.cpp's 17.5441 over the same 20 chunks (ratio 0.999; every chunk within 1.2 %) ->
   ACCEPT.** The port is faithful; the model's Wikipedia perplexity is genuinely twice Qwen3.5-9B's, and G2's limit was
   too tight for its training mix. A first verdict computed on a 4-chunk partial (a waiter keyed to a misplaced PID
   file) was discarded before use; the verdict script now refuses fewer than 20 chunks.

## Results (M1, greedy, thinking off, bare-answer rule; same build, card and flags for SNL and Q35R)

| | SenseNova-Loop-9B (SNL) | Qwen3.5-9B (Q35R) | SNL - Q35R, 95 % CI |
|---|---|---|---|
| invented questions declined (of 100) | **53** | 65 | **-0.12 [-0.22, -0.03]** |
| hard questions right / wrong / declined (of 100) | **14** / 78 / 7 | 42 / 53 / 4 | right **-0.28 [-0.37, -0.19]** |
| easy questions right (of 40) | 27 | 36 | -0.225 [-0.375, -0.075] |
| unfinished | 2 | 3 | |
| median output tokens; decode speed | 46; **19 tok/s** | 52.5; 57 tok/s | |

| | result |
|---|---|
| H1 SNL declines fewer invented questions (0.55) | **holds:** 53 vs 65 |
| H2 looping buys no facts: hard accuracy at most +0.05 (0.6) | **holds, far beyond the prediction:** 14 vs 42 -- but two different models cannot separate looping from training; the loop-count dial could |
| E1 the PR head's shared caches change >= 24 of 240 answers (0.6) | **holds:** 209 of 240 answers differ (35 grades); SNLH 50 / 13 / 25 on the three rows above; wikitext +2.4 % |
| Replay (added after the result, not preregistered): SNL again on `4bc61eed7` (arm SNL2) | **240 of 240 answers identical** -- the faithful build is deterministic, so all 209 changes are the shortcut's |

Read by hand, several easy misses are clear errors: Daegu for North Gyeongsang (its capital before 2016), Leoncavallo
for *Cavalleria rusticana*, an invented "San Juan de Los Lagos" for Guarico. Others are dating disputes the key may not
settle (*David Copperfield* 1849 against 1850, Kabul University 1932 against 1931); both arms are scored on one key. Reported, not a gate: Q35R on this build and
card against the stored Q35B (.194 P100, CUDA build 67107ac34f): 160 of 240 answers identical, 227 grades identical,
the totals equal or within 3 (invented 65 / 65, hard 42 / 42, easy 36 / 33).

Replay script `run_replay.sh`, comparison `summary_replay.txt`.

## Reading

1. **A strong agent is not a knowledgeable one.** SenseNova-Loop-9B's card puts it level with Qwen3.8-27B on several
   agent benchmarks (lower on NL2Repo), yet on short factual questions it knows a third of what Qwen3.5-9B knows, answers wrongly more (78 hard
   wrong against 53), and declines fewer invented questions. Its doubled English Wikipedia perplexity, confirmed on the
   reference, points the same way: most likely its training went to agent work, code and other languages, not English
   trivia. Two different models cannot say whether the loop itself plays any part; running the same weights at 1, 2
   and 3 loops could.
2. **The port is right; the newest commit is not neutral.** At `4bc61eed7` llama.cpp matches SenseTime's own code to
   0.1 % in perplexity. The PR head (`0ba8e4adf`, 11-22), which lets the second loop reuse the first loop's
   full-attention cache where the reference keeps one per pass, rewrites most greedy answers (209 of 240, usually from
   the first sentence) while the totals move only by a few.
3. **It is slow here:** 19 tokens per second against 57 for Qwen3.5-9B on the same card, more than the 1.75x extra
   layer work explains.

## Limits

Thinking off and greedy (the model's own example runs thinking on); two loops, the default; one quant (the official
Q8_0); M1 is short English factual questions; lineage not stated, so this compares two models, not a fine-tune against
its base. The Q35R-Q35B comparison mixes a build change with a backend change, so it is only a preview of the planned
three-stack drift test.
