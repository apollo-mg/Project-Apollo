# Pre-registration — does brevity training cost false-premise detection?

**Logged 2026-09-12 ~00:30, before the model finished downloading and before any generation.**

## The question

Three Qwen3.8-27B tunes now sell the same thing — thinking less. DavidAU's Twin-Turbo, Jackrong's
Qwopus-Flash, and UkisAI's Swift, the last of which states it borrows a transfer component from
BottleCap's ThinkingCap. Tonight we produced the *mechanical* version of the same intervention: a
220-token thinking cap (`RESULT_OVERTHINK_INJECTION_IQ3M.md`, arm B).

**Swift is the trained analogue of that cap.** Same intended effect, applied in the weights instead
of at the decoder. This asks whether they behave the same, and specifically whether brevity is free.

## The mechanism under test

`RESULT_SEARCH_ASYMMETRY.md`: *deliberation is a search; it terminates on a hit when a target exists
and runs until something is constructed when none does.* Abstaining on a false premise therefore
**requires** the long deliberation that brevity training removes.

That predicts a specific, asymmetric cost: brevity should be nearly free on answerable questions and
expensive on unanswerable ones. Tonight's bare-cap probe is one instance — capped at 250 tokens, the
base model answered *"tungsten … W"* for an element that does not exist.

**Swift's own card is consistent without saying it:** AIME 2026 −4.67 and HMMT −3.33 against base,
its two worst rows, and both are the benchmarks that need long search.

## Arms

| arm | model | thinking |
|---|---|---|
| **SWIFT** | `bartowski/ukisai_Swift-Qwen3.8-27b-GGUF` → `IQ3_XXS` (12.32 GB), sha256 in `swift/manifest.txt` | unrestricted |
| **BASE** (already collected) | `Qwen3.8-27B.i1-IQ3_M` arm A from `overthink/`, 2026-09-11 | unrestricted |

Same 16 CAL items, 3 reps, card sampling at `xhigh`, seeds 1001–1003, same
`run_fixture_structfix.py`, same 9070 at 330 W, `-c 16384`, q8_0 KV.

**Declared differences, not controlled:**
- **Quant level and packager.** SWIFT is bartowski `IQ3_XXS`; BASE is mradermacher `i1-IQ3_M`.
  Swift's own `IQ3_M` is 14.9 GB and does not fit the 9070 beside a 16k context, so a matched-level
  comparison is not available on this card. A base `IQ3_XXS` control is queued if the result
  warrants it.
- **`RESULT_COMPLEXITY_CONFOUND.md` applies in spirit:** two models differing on more than one axis
  cannot attribute a difference to either axis alone. This is a screen, not an attribution.

## Predictions

| id | prediction | conf |
|---|---|---|
| P-S1 | **SWIFT confabulates more than BASE on the unanswerable arm** (WRONG + NO-STOP; BASE was 4/24) | 65% |
| P-S2 | SWIFT's answerable arm is not materially worse: ≥ 21 of 24 correct (BASE 23/24) | 70% |
| P-S3 | SWIFT's median thinking on the unanswerable arm is shorter than BASE's 2,275 chars | 80% |
| P-S4 | SWIFT produces no NO-STOP runaway (BASE had 1) | 65% |
| P-S5 | The asymmetry holds: SWIFT's thinking is reduced **more** on the unanswerable arm than on the answerable arm, in percentage terms | 55% |

**P-S1 is the load-bearing one.** If it holds, brevity training buys speed on answerable work and
pays for it in false-premise detection — the failure that is hardest to notice, because it arrives
as a confident answer rather than a timeout.

**If P-S1 fails**, that is the more interesting result: it would mean trained brevity avoids the
cost that a mechanical cap imposes, i.e. the model learned *when* to stop rather than merely *to*
stop. That would be a genuine argument for the tune over the flag.

## Power

24 unanswerable generations. BASE failed 4/24. Detecting an increase to ≥ 12/24 is comfortable by
Fisher exact; smaller shifts are not resolvable, and the report will say so rather than reading a
trend. **The same floor-effect warning as tonight applies:** the CAL corpus proved easy at 3-bit.

## What will not be claimed

- Nothing about Swift's benchmark scores, which we are not reproducing.
- Nothing about DavidAU or Qwopus, which are different tunes and untested here.
- No attribution to brevity training specifically over quant level or packager, per the declared
  differences.
- Nothing about answerable-question quality beyond this 8-item tier.
