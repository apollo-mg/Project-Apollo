# Pre-registration: do DavidAU's Turbo-Brilliance reasoning modes buy anything but length, and does one stray template token matter?

**Registered 2026-09-28, before any CAL row was generated.**

**What has run so far, all of it setup:**
- the GGUF was fetched (sha256 matched Hugging Face's record);
- per-mode render sizes were measured;
- one exploratory call on "17*19" each in `off`, `high` and `omni` (all correct; 349 / 412 / 2,001 completion
  tokens);
- the template whitespace was bisected.

**Prior art checked:** `ledger_precheck.py "chat template reasoning mode einstein DavidAU system prompt effect"`. It
found:
- `davidau-templates/RESULT_TEMPLATE_MINJA_DIFF.md` (09-13): minja and jinja2 disagree on DavidAU's Qwen3.8
  templates, and the Frogger template's reasoning modes were broken in both;
- `viability/RESULT_EINSTEIN_TERMINATION.md` (09-12): on Qwen3.8-27B, `einstein` never ran away (0/24) while the
  template's default effort did (5/24);
- `viability/RESULT_EFFORT_IS_A_PROMPT_EDIT.md`: an effort setting is a system-prompt rewrite.

**What this adds:**
- a different model family (LiquidAI LFM2.5, 2.6B) and DavidAU's newest mode system (12 modes);
- **a whole mode sweep on one graded item set**, where the prior work was one mode;
- a controlled **single-token template A/B**: the smallest template difference there is, next to the largest (mode
  prompts up to 995 tokens).

## Model, host, engine

- **Model:** `DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilliance-Power-X12-NEO-MAX-GGUF`,
  `LFM2.5-2.6B-Q3.8-TBrilliance-NEO-MAX-Q8_0.gguf`, sha256 `524dbaa84e79…837e` (matches the Hugging Face LFS record).
- **Host:** RX 9070 XT desktop.
- **Engine:** upstream llama.cpp `58367713a` (`/mnt/TG_2TB/AI/llama_upstream/build_rocm`), `-ngl 99 -c 32768 -np 1
  --jinja -fa on`.
- **Servers:** two, one per template.
  - **ORIG** on :8095 uses the template embedded in the GGUF.
  - **TRIM** on :8096 uses `--chat-template-file` produced by `make_trimmed_template.py`.

## The template finding the A/B is built on

Every render of the embedded template, in every mode including `off`, is `<|startoftext|>` + **`\n\n` (token 8)** +
`<|im_start|>…`. LiquidAI's base template renders `<|startoftext|><|im_start|>`.

Bisection with jinja2, set up as llama.cpp and transformers set it up (`trim_blocks` and `lstrip_blocks`; verified
byte-identical to llama-server's `/apply-template` in all modes tried) finds two sources:
- lines **97** and **485** of the template, both comment tags `{#` placed after trimmed code, each leaking one
  newline;
- left-trimming exactly those two (`{#-`) removes the token and nothing else. **58/58 renders** are byte-identical
  apart from the removed newlines (all 14 modes, their instruct variants, multi-turn, thinking on and off).

## Design

- **Items:** the 16 CAL items and the CAL tier prompt of `viability/fixture_v0_beta.json`: 8 answerable, 8
  unanswerable, each unanswerable item paired with a real member of its category. The prompt sanctions `UNKNOWN`.
  The user message is `{REASON:<mode>} ` + the prompt.
- **Arms:**
  - ORIG: `off, low, high, ultra, einstein, spoon, omni`. `high` is the template's default.
  - TRIM: `off, high, omni`.
- **Sampling:** DavidAU's published tester settings: temp 1.0, top_k 64, min_p 0.05, top_p 0.95, repeat penalty
  1.0. `max_tokens` 16,000; `cache_prompt: false`, following the card ("NO caching") and our determinism receipts.
  Seeds 1001, 1002 and 1003 per request, three per (arm, mode, item).
- **Size:** 10 cells × 16 items × 3 seeds = **480 generations**. Order interleaves modes and templates inside each
  (seed, item).
- **Grading:** the fixture's own `pick_answer()` (the last `Exact Answer:` wins; content is preferred over
  reasoning) and `classify()`. `finish_reason == length` is NO-STOP. Transport errors are rows with grade ERROR and
  are never skipped.
- **Gate G1** runs before any row, and the driver aborts on failure:
  - every mode's tag is stripped from the render;
  - each mode's injected prompt has its registered token count (off 18, low 76, high 170, ultra 345, einstein 320,
    spoon 822, omni 995 on ORIG; TRIM exactly one fewer);
  - the TRIM template carries the edit and ORIG does not;
  - both servers serve the same file.

## Readouts (`analyze_lfm25_modes.py`, committed with this file, self-tested on synthetic rows)

Per cell: answerable CORRECT of 24, unanswerable ABSTAINED of 24, NO-STOP, ERROR, parse-suspect rows (more than one
`Exact Answer:`), and median completion tokens.

**Power:** with 24 attempts per rate, the tests below can only detect differences of roughly 0.3 in a rate. A "no
difference" result means no LARGE effect.

## Predictions

| # | claim | rule | confidence |
|---|---|---|---|
| P1 | **The big modes cost far more** | median completion tokens: omni ≥ 3× high, spoon ≥ 3× high, and low ≤ high | 0.75 |
| P2 | **No mode buys accuracy** | no mode's answerable CORRECT beats `off`: one-sided Fisher p ≥ 0.05/6 for all six (Bonferroni) | 0.7 |
| P3 | **The heavy frameworks confabulate more** | omni + spoon + einstein pooled abstain less on unanswerable items than `off`: one-sided Fisher p < 0.05 **and** ≥ 0.10 lower | 0.3 |
| P4 | **The stray whitespace token is inert** | for off, high and omni: TRIM vs ORIG two-sided Fisher (answerable CORRECT, unanswerable ABSTAINED) and Mann-Whitney (tokens) all p ≥ 0.05/9 (Bonferroni) | 0.7 |

Reported without a prediction:
- NO-STOP counts;
- the `einstein` and `ultra` cells;
- per-item patterns;
- the card's claims that outputs run "2k to 12k+" and that stating an output length is obeyed. The latter is not
  tested.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
