# RESULT: a science-reasoning distillation made Qwen3.5-9B reason worse, not better -- 20 points lower on GPQA Diamond -- and, once it thinks, it makes up answers to invented questions 40 times in 100 where its base does 6

**Prereg:** `PREREG_SCI_DISTILL.md` (`f4a04329`; Addenda 1-3 and Deviations 1-2, each committed before the rows it
concerns; Deviation 1 was recorded after the fine-tune's first three GPQA rows and before any base GPQA row). **Run:**
2026-11-09 13:35 to 11-10 18:44 on .194, llama.cpp `67107ac34f` build_sm60, every server on one P100 at 1,063 MHz and
150 W. Chains: `run_sci_distill.sh`, `run_sci_m1think.sh`, `run_sci_m1samp.sh`; logs in `raw/`. All gates passed.
**Numbers:** `RESULT_gpqa_regraded.json`, `RESULT_gpqa.json` (registered grade), `RESULT_m1.json`,
`RESULT_m1_thinking.json`, `RESULT_m1_<A>_vs_<B>.json`, `RESULT_m1_2x2.json`. **Raw:** M1 rows in
`quant-abstention/raw/main_{Q35B,Q35BS,Q35BT,DSV9,DSV9S,DSV9T}.jsonl`; GPQA rows text-free in `raw/gpqa_*.jsonl`
(full replies kept outside the repo, as registered).

**Files:** Qwen3.5-9B (`Qwen/Qwen3.5-9B` @ `c2022362`, byte-identical shards to `unsloth/Qwen3.5-9B`) and Jackrong's
DeepSeek-V4-Pro-Qwen3.5-9B (@ `7d7edca1`), both converted here to Q8_0 with one converter and `--no-mtp`: 9,527,501,408
and 9,527,502,400 B, sha256 `f904644b...` and `3621845d...`; the tensor map shows 0 differences. Both token gates
(240 M1 prompts thinking off, 792 GPQA prompts thinking on) printed identical hashes on both models.

## 1. Mark's hypothesis: does a science distillation reason better? No -- worse.

GPQA Diamond, 198 items, thinking on, Qwen's thinking sampling, 30,000-token cap, rounds 1-3 (594 requests per model).
Graded with the Deviation 1 fallback (a bare final letter counts when the `ANSWER:` line is missing):

| | Qwen3.5-9B | DeepSeek-V4-Pro distill | distill - base [95 % CI] |
|---|---:|---:|---:|
| **accuracy** | **0.806** | **0.609** | **-0.197** [-0.242, -0.150] |
| accuracy on the 133 items never truncated in either model | 0.882 | 0.792 | -0.090 [-0.133, -0.048] |
| hit the 30,000-token cap | 2.2 % | 19.2 % | |
| median completion tokens | 10,208 | 6,372 | ratio 0.62 |
| mean completion tokens | 11,766 | 11,740 | |
| tokens per correct answer | 14,591 | 19,264 | 1.32x |
| accuracy: physics / chemistry / biology | 0.94 / 0.70 / 0.70 | 0.79 / 0.46 / 0.53 | |

- **Worse everywhere,** in all three domains, and still 9 points worse where neither model ran out of budget.
- **The runaways do not look like loops.** A tail check of the 114 capped traces (about 100,000 characters each)
  found no verbatim repetition, and the two I read are endless re-deliberation ("actually... wait... no...") that never
  commits. Temperature 1.0 and a presence penalty were already on, as Qwen recommends. That sampling does not fix this
  kind of runaway is an inference (there is no greedy GPQA arm); Sage's greedy loops, by contrast, mostly vanished
  under sampling.
- **Efficient when it knows, unable to tell when it does not.** Right answers took a median 3,064 tokens (the base:
  9,382); wrong ones 28,965 (the base: 14,563). Among replies that FINISHED, length flags a wrong answer only weakly
  (AUROC 0.60 for the distill, 0.68 for the base); with the capped replies included, 0.80 and 0.72, which is partly
  circular because a capped reply is wrong by definition. As a budget it separates clearly: a distill reply finished
  within 8,000 tokens is right 81.5 % of the time, one not finished by then 35.5 %; for the base the same cut gives
  92.1 % vs 74.7 %, so the useful cutoff is model-specific. The card's efficiency claim is true only for questions the
  model can answer; over all questions it spends a third more tokens per correct answer.
- **It also drops the answer format:** 71 % of its replies end with a bare letter instead of the requested `ANSWER: X`
  line (the base: 0 %). By the registered grade it scores 0.032. A further 33 of its 594 finished replies carry no
  answer either rule recognizes (26 say "Option Selected: X", a few are garbage); the primary grade stays as
  registered, and counting those 26 as answers would move it from 0.609 to 0.626 (10 of them are right).

## 2. The cost side: M1, two decoding modes x two thinking modes per model

| arm | thinking | decoding | easy right | hard right | hard refused (bare) | invented refused (bare) | invented made up | median tokens |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Q35B | off | greedy | 0.82 | 0.42 | 0.03 (0.00) | 0.65 (0.00) | 0.35 | 52 |
| Q35BS | off | sampled | 0.80 | 0.38 | 0.06 (0.00) | 0.68 (0.00) | 0.29 | 70 |
| Q35BT | on | sampled | 0.82 | 0.39 | 0.12 (0.00) | **0.94** (0.00) | **0.06** | 2,561 |
| DSV9 | off | greedy | 0.70 | 0.26 | 0.40 (0.39) | 0.85 (0.81) | 0.15 | 2 |
| DSV9S | off | sampled | 0.48 | 0.07 | 0.66 (0.65) | 0.93 (0.93) | 0.07 | 2 |
| DSV9T | on | sampled | 0.72 | 0.34 | 0.05 (0.02) | **0.58** (0.33) | **0.40** | 418 |

"Refused" counts the registered ABSTAINED grade plus bare "UNKNOWN" replies; "(bare)" is the bare share alone.

- **With thinking off, the distill's non-thinking mode has collapsed.** It answers most items with the single word
  "UNKNOWN" (median reply 2 tokens), including 39 % of real hard facts and some easy ones; sampled, worse still (hard
  right 0.07). Its forced answer slot leans toward UNKNOWN LESS than the base's (0.53 vs 0.79 on invented items), so the
  free-text refusals are a reply-style collapse, not caution. Trained only on thinking traces, it lost the other mode.
- **With thinking on, the fine-tune pattern returns, larger than in any earlier case.** Hard facts are roughly level
  (0.34 vs 0.39, -0.05 [-0.12, +0.02]), but it makes up answers to 40 of 100 invented questions where the base, thinking,
  makes up 6: refused (bare counted) 0.58 vs 0.94, -0.36 [-0.46, -0.25], flips 3 vs 39.
- **Thinking changes honesty, not knowledge (base, sampling held fixed):** hard right 0.38 -> 0.39 (+0.01 [-0.05,
  +0.08]); invented refused 0.68 -> 0.94 (+0.26 [+0.18, +0.35], flips 26 vs 0); made up 0.29 -> 0.06.
- **Greedy vs sampled barely matters with thinking off (base):** invented refused 0.65 vs 0.68 (+0.03 [-0.05,
  +0.11]), hard right 0.42 vs 0.38 (n.s.). So the base's 0.65 -> 0.94 is thinking, not sampling.

## Predictions

| # | claim | result |
|---|---|---|
| P1 | cost side: U refused DSV9 - Q35B <= -0.05 | **held by the letter, for the wrong reason:** -0.61 on the strict grade because bare "UNKNOWN" scores NO-ANSWER; counting bare refusals it is +0.20 (the collapse). With thinking on (P8) the pattern is real |
| P2 | no general facts added: H DSV9 - Q35B <= +0.02 | **held:** -0.16 (mostly bare refusals of facts it knows when thinking) |
| P3 | Mark's hypothesis: GPQA DSV9 - Q35B >= +0.05, CI lower > 0 | **failed:** -0.197 [-0.242, -0.150] |
| P4 | efficiency transfers: GPQA median tokens ratio <= 0.7 | **held by the letter (0.62), contradicted in substance:** mean tokens equal, tokens per correct 1.32x |
| P5 | no accuracy cost: GPQA DSV9 - Q35B >= -0.03 | **failed:** -0.197 |
| P6 | the mode, not lost knowledge: H DSV9T - Q35BT >= -0.05 | **held, at the boundary:** -0.05 |
| P7 | the collapse is a non-thinking effect: DSV9T bare UNKNOWN on H <= 0.10 | **held:** 0.02 |
| P8 | the fine-tune pattern under thinking: U refused (bare counted) DSV9T - Q35BT <= -0.05 | **held:** -0.36 |
| P9 | thinking does not change knowledge: \|H Q35BT - Q35BS\| <= 0.05 | **held:** +0.01 |
| P10 | thinking does change abstention: \|U Q35BT - Q35BS\| >= 0.10 | **held:** +0.26 |
| P11 | greedy vs sampled barely matters, thinking off: \|U Q35BS - Q35B\| <= 0.05 | **held:** +0.03 |

## What this adds

1. **The first benefit-side test of a fine-tune in this repo, and it failed:** a science-reasoning distillation from a
   frontier teacher made a 9B worse at graduate science reasoning, by 20 points, while its card reports +0.93 on
   MMLU-Pro at an 8K cap. The difference is not explained by budget: the distill is 9 points behind even where neither
   model ran out.
2. **The largest drop in refusal of invented items measured here (-0.36), but in thinking mode,** a condition none of
   the five earlier fine-tunes were compared in (they ran thinking off). On the thinking-off comparison the series uses,
   this one cannot be counted: its non-thinking mode is broken and refuses MORE (+0.20 with bare replies). So the series
   stays at five of five with thinking off, plus this thinking-mode case. Granite's IDK adapter, trained for abstention,
   is still the only one to raise refusal of invented items, but with bare "UNKNOWN" counted it also refuses 38 % (4.1)
   and 69 % (4.2) of REAL hard facts, which the scorecard's strict over-refusal metric had hidden (corrected 11-10:
   `honesty.overabstain_hard_lenient`, read by the map and badges).
3. **For the HF #23 critiques (SerialKicked, 11-09), on this model:** thinking does not change knowledge recall (he was
   right), but it changes abstention a lot (+0.26), and greedy vs sampled makes no measurable difference with thinking
   off. This also suggests, without proving, that Sage's 0.45 -> 0.85 was mostly thinking rather than sampling.
4. **Stopping is a separate skill, and distillation breaks it:** the distill learned the teacher's long self-checking
   without the ability to finish it (GPQA) and the short confident answer without the check that a thing exists (M1).
   A token budget separates right from wrong well, with a model-specific threshold; length among finished replies is a
   weak signal.
5. **A model trained only on thinking traces can lose its non-thinking mode entirely,** and no thinking-mode benchmark
   will show it.

## Limits

One model pair, Q8_0, single-GPU P100 servers. GPQA: 198 items, 3 rounds, resolves about 5 points. M1 sampled arms are
K = 1 per item. The GPQA primary uses a post-hoc, format-only fallback grade (Deviation 1); the registered grade is
reported and differs only by answer format. A few GPQA requests started after the 24 h stop (Deviation 2: a runner
slot-starvation bug, fixed afterwards: one dispatcher now hands out work in order and checks the stop when a request
starts; `tests/test_gpqa_runner.py` fails on the old runner and passes on the fixed one). Concurrent slots make GPQA samples not
bit-reproducible.
