# Result -- DavidAU's Turbo-Brilliance modes buy no accuracy and cost calibration: the template's DEFAULT mode refuses 7/24 invented questions where no system prompt refuses 20/24. And one stray whitespace token cuts output length by 37-45 % in the modes that carry a system prompt.

**2026-09-28.** Pre-registration `PREREG_LFM25_MODES.md` (`a6d260f`); driver `lfm25_modes.py`, gate G1 passed before
any row; analysis `analyze_lfm25_modes.py` (committed with the prereg, self-tested on synthetic rows). Raw
`lfm25_modes/rows.jsonl`: 480 rows, 0 errors. Run log `lfm25_modes_run.log`.

- **Model:** `DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilliance-Power-X12-NEO-MAX-GGUF`, NEO-MAX Q8_0, sha256 `524dbaa8…837e`.
- **Engine:** upstream llama.cpp `58367713a` on the RX 9070 XT, ~140 tok/s.
- **Items and sampling:** the 16 CAL items (8 answerable, 8 unanswerable twins) with a sanctioned `UNKNOWN`, at
  DavidAU's tester sampling (temp 1.0, top_k 64, min_p 0.05, top_p 0.95), 3 seeds per item.

## Results

| template / mode | injected prompt (tok) | answerable correct | **unanswerable refused** | median tokens | parse-suspect | NO-STOP |
|---|---:|---:|---:|---:|---:|---:|
| ORIG / **off** | 18 | 24/24 | **20/24** | 504 | 0 | 0 |
| ORIG / low | 76 | 22/24 | **6/24** | 210 | 0 | 0 |
| ORIG / **high (the default)** | 170 | 19/24 | **7/24** | 614 | 2 | 0 |
| ORIG / ultra | 345 | 20/24 | 13/24 | 1,216 | 13 | 0 |
| ORIG / einstein | 320 | 21/24 | 11/24 | **6,371** | **27** | 1 |
| ORIG / spoon | 822 | 19/24 | 11/24 | 1,274 | 19 | 0 |
| ORIG / omni | 995 | 23/24 | 17/24 | 2,093 | 1 | 0 |
| TRIM / off | 17 | 23/24 | 19/24 | 568 | 1 | 0 |
| TRIM / high | 169 | 20/24 | 7/24 | 340 | 0 | 0 |
| TRIM / omni | 994 | 23/24 | 9/24 | 1,321 | 2 | 0 |

"Parse-suspect" is a row with more than one `Exact Answer:` line; the grader takes the last. It is common in the
panel modes (einstein, spoon, ultra), so their grades are less certain than the others'.

## Registered verdicts

| # | claim | result |
|---|---|---|
| P1 | omni and spoon >= 3x high tokens; low <= high | **does not hold.** omni 3.4x and low 0.34x pass; spoon is 2.1x. einstein, not predicted, is 10.4x |
| P2 | no mode beats `off` on answerable accuracy (Bonferroni over 6) | **holds.** `off` is 24/24; every one-sided p = 1.0 |
| P3 | the heavy frameworks (omni + spoon + einstein) refuse less than `off` on unanswerable, p < 0.05 and >= 0.10 lower | **holds.** 39/72 vs 20/24, p = 0.009, 0.29 lower |
| P4 | the stray `\n\n` token is inert (off, high, omni; 9 tests, Bonferroni 0.0056) | **does not hold.** Length: high p = 0.005, omni p < 0.001, off p = 0.34. Grades: none significant after correction (omni refusals 17 -> 9, p = 0.041 uncorrected) |

## What it means

- **The template's default mode makes the model confabulate.**
  - With no tag the template applies `high`. It refuses **7/24** invented questions, against **20/24** with no
    system prompt at all (one-sided Fisher p = 0.00018).
  - `low` is worse at 6/24 (p = 5.5e-05). `einstein` and `spoon` drop to 11/24 (p = 0.007), `ultra` to 13/24
    (p = 0.03).
  - Only `omni` stays near `off` (17/24, p = 0.25), at 4x the tokens.
  - The modes buy nothing on the answerable half: `off` already answers all 24 correctly, and none beats it.
  - On a task with a sanctioned "I don't know", every mode except omni trades honesty for nothing.
- **Einstein is expensive and messy here:** a median of 6,371 tokens (12.6x `off`), 27 of 48 rows with several
  competing final answers, and the sweep's only runaway. On Qwen3.8-27B (`viability/RESULT_EINSTEIN_TERMINATION.md`)
  einstein never ran away. On this 2.6B it once did, and it rarely commits to one answer.
- **One whitespace token moves output length.**
  - The embedded template leaks `\n\n` after `<|startoftext|>` (lines 97 and 485: two comment tags placed after
    trimmed code). LiquidAI's own format has nothing there.
  - Removing it, a two-character fix otherwise byte-identical on 58/58 renders, shortens the modes that carry a
    system prompt: `high` median 614 -> 340 (unanswerable 0.52x), `omni` 2,093 -> 1,321 (unanswerable 0.45x).
  - With no system prompt (`off`) nothing significant moves.
  - Whether it changes answers is not settled at this n. `omni`'s refusals fall 17 -> 9 (p = 0.041), which does not
    survive the correction.
  - Answer to "how much difference is in a chat template": **the injected text swings refusal from 83 % to 25 %,
    and a single token nobody meant to put there changes how long the model thinks by ~40 %.**
- **The two-character fix is worth sending upstream** (`make_trimmed_template.py` does exactly it). This receipt
  does not show it makes the model better, only different. The fixed version is the one that matches LiquidAI's
  trained format.

## Not established

- **One kind of task.** Short factual questions with an abstain option. The modes are sold for research, planning
  and creative work, which this set does not test. "No accuracy gain" is at a ceiling (`off` 24/24), so it cannot
  show a gain if one existed.
- **Small n.** 16 items x 3 seeds. The large refusal drops are far outside the noise; P4's grade effects are not.
- **Temp 1.0.** A one-token prompt change reseeds every trajectory: same-seed grades agree on 42/48 (off), 35/48
  (high) and 31/48 (omni). That is expected divergence, not an effect. The effects claimed are distribution shifts.
- **Mechanism.** Why a leading `\n\n` shortens system-prompt modes and not `off` is not tested.
- **One model, one quant, one engine.**

## Reported upstream

2026-09-28: Mark posted both findings (the two-character template fix, and the default mode lowering abstention) to
the model's community tab, with this receipt linked:
https://huggingface.co/DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilliance-Power-X12-NEO-MAX-GGUF/discussions/11
