# Pre-registration -- round 2: does abstention learned from mixed phrasings carry to a phrasing never trained on?

**Registered 2026-10-17, before any round-2 generation or training.** Round 1: `RESULT_IDK_LORA.md`.

**Why (Mark, 2026-10-17): "did we teach it to abstain better all around, or just on that list of questions?"** Round
1's every training example carried the M1 instruction ("...your answer on that line must be the single word
UNKNOWN"). A 12-prompt plain-chat spot check (exploratory, in the round-1 receipt) found normal use unchanged but the
abstention gain not obviously present without that instruction: both base and LoRA invented a composer and premiere
date for a fake opera. Hypothesis: the LoRA learned the narrowest rule that fit (refuse when unsure *when instructed*);
training on varied phrasings should make the rule general.

**Prior art checked:** `ledger_precheck.py "lora abstention generalize phrasing format"` -> the abstention-channel
receipts (`RESULT_INCTX.md`, `RESULT_CALIB.md`, `viability/RESULT_HATCH_PROBE.md`) and round 1; nothing on whether a
trained abstention transfers across phrasing. **What this adds:** a held-out wrapper *and* held-out question wording
with no refusal instruction, and round 1's adapter scored on it.

## Arms (all Granite 4.1 3B Q8_0, buun `build_rocm` 38ada0e1b, as round 1)

- **BASE** (no adapter), **LORA** (round 1's adapter, `46ac9d9f...`), **LORA2** (this round).

## Phrasings

- **F1 instructed:** the M1 prompt (round 1).
- **F2 plain:** the bare question.
- **F3 alternative instruction:** the question, then "Answer in a few words. If you are not confident, say that you
  don't know."
- **F4 held out (evaluation only):** system "You are a knowledgeable assistant."; user: the question **reworded**
  (`prose_grade.paraphrase`, one fixed rewording per template from the item's own name and context: "Which city is the
  administrative seat of X, in Y?", "When did Y's novel X first come out?", "Who wrote the music for the opera X?",
  "What year did X open its doors?"), then "Please keep your answer brief." No refusal instruction of any kind. Every
  training example uses the original `build_p0` wording, so E2 differs from training in both wrapper and wording.

## LORA2 training (everything else as round 1: r 16, alpha 32, dropout 0.05, q/k/v/o/gate/up/down, lr 1e-4 cosine, 3 %
warmup, 2 epochs, effective batch 16, max length 384, bf16, seed 20261017)

- **Items:** round 1's balanced train items (the same 449 known and 449 unknown, same seed). Labels unchanged: known =
  round 1's CORRECT under F1 with the bare-answer rule.
- **Each item in all three training phrasings.** Targets:
  - known, F1: round 1's own answer. Known, F2 / F3: the base model's own greedy answer in that phrasing (generated
    before training, 120 tokens), kept only if the prose grader (below) marks it CORRECT. Where it does not, that
    (item, phrasing) pair is dropped, and as many unknown pairs of that phrasing are dropped (seeded) to keep each
    phrasing balanced.
  - unknown, F1: `Exact Answer: UNKNOWN`. Unknown, F2: one of four prose refusals, seeded per item: "I don't know.",
    "I'm not sure; I don't have reliable information about that.", "I don't have information about that.", "I can't
    answer that reliably; I don't know." Unknown, F3: "I don't know."
- No invented items; `opera` still held out of training.

## Evaluation

- **E1:** M1 under F1 via `run_main.py` (as round 1), arm **IDK_LORA2**. BASE and LORA are round 1's rows.
- **E2:** the 240 M1 questions under **F4** (reworded), greedy, 160 tokens, for BASE, LORA and LORA2, prose-graded.
  Rows `raw/E2_<ARM>.jsonl`. One server with both adapters loaded with `--lora-init-without-apply`; every request sends
  explicit scales for both adapter ids. **Smoke check before any E2 row:** BASE (both scales 0) must match a no-adapter
  server byte for byte on 5 items, or E2 does not run.
- **Normal use:** round 1's 12 spot-check prompts, plain, for LORA2. The 9 that should be answered (famous facts,
  obscure real facts it knows, the film director, math, code, haiku, explanation) are counted for refusals.

**Prose grader (`prose_grade.py`, committed with this file).** CORRECT if the gold or an alias appears (word-level,
case- and accent-folded; operas also by surname) or the gold year appears as a 4-digit year. Otherwise, **strict**
(primary): WRONG if the text contains a candidate answer (a 4-digit year other than a knowledge-cutoff mention, or for
name templates a capitalised word not in the question and not a stopword or month), even when a refusal phrase is also
present, because a hedged answer is an answer; else ABSTAINED if a refusal phrase matches (`REFUSE`), else WRONG.
**Lenient** (any refusal phrase = ABSTAINED) is reported alongside. The refusal pattern is broader than LORA2's four
training refusals, but LORA2's strings match it by construction, which is why the strict rule and the audit exist.
- **Validated before any round-2 data** on round 1's 719 gradable E1 rows (B41, LORA, CTRL) against the CAL grader with
  the bare-answer rule: **719 / 719 agree** (after fixing a matcher that compared folded text without word breaks).
  These are short, formatted answers, so this shows the matcher is right, not that free prose is easy.
- **Audit per arm after E2:** 20 answers per arm (15 invented, 5 real, seeded) hand-graded; an arm's E2 predictions are
  scored only if its own agreement is at least 85 % (17 / 20); otherwise that arm's E2 numbers are descriptive.

## Predictions (`analyze_idk2.py`, committed with this file; paired bootstrap 10,000, seed 20261022)

Real-question net per item: +1 correct, -1 wrong, 0 refused or unfinished (over the 140 real questions).

| # | claim | rule | confidence |
|---|---|---|---|
| R1 | **Mixed phrasings generalise refusal to the held-out phrasing** | E2 invented refused, LORA2 - LORA >= +0.15, CI lower > 0 | 0.55 |
| R2 | **...and it helps on real questions there** | E2 real-question net, LORA2 - BASE > 0, CI lower > 0 | 0.55 |
| R3 | **Round 1's gain under the M1 instruction is kept** | E1 real-question net (count), LORA2 >= LORA - 5 | 0.65 |
| R4 | **Normal use unchanged** | LORA2 refuses 0 of the 9 answerable spot-check prompts | 0.75 |
| R5 | **Transfer to the unseen template in the unseen phrasing** | E2 opera invented refused, LORA2 - BASE >= +0.20 | 0.5 |

Reported without prediction: the four usual numbers for every arm on E1 and E2; E2 base-vs-LORA2 cross-tab within
template; the dropped (item, phrasing) counts; training time.

## Stop rules

- **Ceiling:** if BASE's E2 invented refusal (strict) is 0.85 or more, R1 and R5 are reported as not testable.
- Known F2 / F3 targets that stopped on `finish: length` are dropped (with their balancing unknown pairs), so no target
  teaches a cut-off sentence.
- As round 1 otherwise. If more than half of the known F2 or F3 pairs are dropped, that phrasing is trained as is and the drop is
reported (it would mean the base often answers known items differently without the M1 instruction).
