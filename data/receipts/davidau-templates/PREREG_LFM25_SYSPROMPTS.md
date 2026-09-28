# Pre-registration: does Qwen3.8's one-sentence `xhigh` prompt do what DavidAU's 4,500-character omni prompt does?

**Registered 2026-09-28, before any row.** A follow-up to `RESULT_LFM25_MODES.md`, prompted by Mark: "I actually quite
like that prompt [omni]. Would be curious to compare it to qwens much shorter xhigh."

**Prior art checked:** this directory's `RESULT_LFM25_MODES.md` (same model, items and sampling);
`viability/RESULT_EFFORT_IS_A_PROMPT_EDIT.md` (xhigh is a system-prompt edit). **What this adds:** the two prompt texts
compared head to head in the same slot on the same model, plus an ablation of omni's adversarial section. That
section was my hypothesis for why omni kept the model honest, and the corrected template already weakens it:
TRIM/omni refused 9/24, not the 17/24 of ORIG/omni.

## Design

- **Model, template and server:** the TRIM server of `RESULT_LFM25_MODES.md` (LFM2.5-2.6B Q8_0 NEO-MAX, the two-char
  whitespace fix), restarted fresh before the run, with one discarded warm-up.
- **Prompt:** every user message carries `{REASON:off}`, so the template injects nothing. The only difference between
  arms is the system message:

| arm | system message | chars | sha256 prefix |
|---|---|---:|---|
| NONE | none | 0 | -- |
| XHIGH | Qwen3.8's xhigh text, verbatim from Flash-Next's template | 207 | `982cfb432c323e6d` |
| OMNI | DavidAU's omni text, exactly as the template injects it | 4,506 | `c7995a73c16f94f2` |
| OMNID2 | OMNI with its "DIMENSION 2" block cut (650 chars). One reference to "Dimensions 1 through 4" is left as is | 3,856 | `29b7d220c2242c0c` |

  OMNI as a system message renders **byte-identically** to `{REASON:omni}` on this server. DavidAU's text is "all
  rights reserved", so only the hashes are committed; the driver checks the texts against them.
- **Items, sampling and grader:** as `RESULT_LFM25_MODES.md`: the 16 CAL items, seeds 1001-1003, DavidAU's tester
  sampling, `max_tokens` 16000, `cache_prompt: false`, the fixture's `pick_answer` and `classify`.
- **Size:** 4 arms x 48 = 192 rows.
- **Gate:** each arm's render carries exactly its system text, and no mode text.

## Predictions (`analyze_lfm25_sysprompts.py`, committed with this file, self-tested on synthetic rows)

| # | claim | rule | confidence |
|---|---|---|---|
| Q0 | **Any system prompt costs refusals here** | XHIGH, OMNI and OMNID2 each refuse less than NONE on unanswerable items: one-sided Fisher p < 0.05/3 | 0.5 |
| Q1 | **The one-liner does omni's job at under half the tokens** | XHIGH vs OMNI: two-sided Fisher p >= 0.05 on refusals and on answerable accuracy, **and** XHIGH median tokens <= 0.5x OMNI | 0.5 |
| Q2 | **Omni's honesty lives in its adversarial section** | OMNID2 refuses less than OMNI: one-sided p < 0.05 | 0.2 |
| Q3 | **Seeded sampling reproduces across a server restart** | OMNI matches the stored TRIM/omni rows (same render, seeds and server config) on grade and completion tokens for >= 46/48 | 0.7 |

**Power:** 24 per rate, as before, so only large effects are detectable.

## Deviations

Any change after the first row gets a numbered Deviation here before the affected rows run.
