# Result -- Qwen3.8's one-sentence `xhigh` prompt does exactly what DavidAU's 4,506-character omni does (refused 10/24 vs 9/24, answerable 24/24 vs 23/24) at 27 % of the tokens. And on this 2.6B, ANY system prompt halves the refusals of invented questions (19/24 with none).

**2026-09-28.** Pre-registration `PREREG_LFM25_SYSPROMPTS.md` (`2982ea2`), driver `lfm25_sysprompts.py` (gate passed),
analysis `analyze_lfm25_sysprompts.py` (committed with the prereg, self-tested). Raw `lfm25_sysprompts/rows.jsonl`,
192 rows, 0 errors.
- **Setup:** LFM2.5-2.6B NEO-MAX Q8_0 (DavidAU's Turbo-Brilliance GGUF) on the TRIM template, mode `{REASON:off}`
  (no injection), on a fresh server; the 16 CAL items x 3 seeds at DavidAU's tester sampling.
- **Variable:** only the system message differs between arms. Texts are identified by sha256 prefix (DavidAU's text
  is "all rights reserved"): XHIGH `982cfb43` (207 chars, verbatim from Qwen3.8 / Flash-Next's template), OMNI
  `c7995a73` (4,506), OMNID2 `29b7d220` (3,856: OMNI minus its "DIMENSION 2" adversarial block).

## Results

| system prompt | answerable correct | invented: refused | median tokens |
|---|---:|---:|---:|
| NONE | 23/24 | **19/24** | 568 |
| XHIGH | **24/24** | 10/24 | **356** |
| OMNI | 23/24 | 9/24 | 1,321 |
| OMNID2 | 22/24 | 7/24 | 1,233 |

| # | prediction | result |
|---|---|---|
| Q0 | every system prompt refuses less than NONE (one-sided Fisher, Bonferroni 0.05/3) | **holds.** p = 0.0086, 0.0038, 0.0006 |
| Q1 | XHIGH does omni's job at under half the tokens | **holds.** Refusals 10 vs 9 and answerable 24 vs 23 (both two-sided p = 1.0); tokens 356 vs 1,321 (0.27x) |
| Q2 | omni's honesty lives in its adversarial section | **does not hold.** OMNID2 7 vs OMNI 9, p = 0.38. The hypothesis from `RESULT_LFM25_MODES.md` is withdrawn |
| Q3 | seeded sampling reproduces across a server restart | **holds.** OMNI (a byte-identical render to `{REASON:omni}`) matches the stored TRIM/omni rows on grade AND completion tokens for 48/48; NONE reproduces the stored TRIM/off counts exactly |

## What it means

- **For a system prompt that says "think carefully", the length is decoration here.** Qwen's one sentence
  ("validate key assumptions, consider plausible alternatives, prioritize correctness…") and omni's five-part
  framework produce the same accuracy and the same refusal rate. Omni spends 3.7x the tokens to get there.
- **On this model the honest configuration is no system prompt at all.** Every system text, from 207 characters to
  4,506, drops refusals of invented questions from 19/24 to 7-10/24. A plausible reading, not tested here: any
  instruction frame makes the 2.6B more eager to produce an answer. It is not a property of any one prompt's content.
- **Seeded runs are fully reproducible on this setup** (llama.cpp `58367713a`, ROCm, `-np 1`, `cache_prompt:false`):
  48/48 identical after a restart, so a rerun of one arm is a real control.

## Not established

- One 2.6B model, one task (short factual Q&A with a sanctioned UNKNOWN), 24 attempts per rate. Whether a larger model
  (Qwen3.8-27B, Flash-Next) shows the same "any system prompt costs refusals" effect is untested. On Qwen the
  `xhigh` text is native, so that test would look different.
- OMNID2 leaves one dangling "Dimensions 1 through 4" reference; the ablation removes content, not structure.
