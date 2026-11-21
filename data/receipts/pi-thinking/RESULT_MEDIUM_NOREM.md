# RESULT: it is the thinking -- at `medium` effort (nothing injected) both models declare all 7 impossible items, almost all before any reminder, in about 70% of xhigh's time; with the reminder off, xhigh still declares every one, at the same step; the read-every-file style comes from thinking as well as from the sentence

**Prereg:** `PREREG_MEDIUM_NOREM.md` (committed before either cell ran). **Run:** 2026-11-20 19:32 to 11-21 05:31 on
.194, `run_medium_norem.sh`, code `621900bf`; log `medium_norem/run.log`. **Records:** `medium_norem/medium/<arm>/`,
`medium_norem/norem/<arm>/`, `medium_norem/probe_<arm>.jsonl`. **Readout:** `summarize_mn.py`, written after the run
(the prereg named the measures and rules), output `medium_norem/summary.txt`. Preflight passed at both efforts on
both servers (medium: 695 tokens, nothing injected; xhigh: 733).

## The decomposition (seed 2: 7 impossible items, 3 twins per arm)

| | BASE declared (unprompted) | PIA declared (unprompted) | twins solved B / P | lane-hours B / P |
|---|---|---|---|---|
| thinking off | 1 (0) | 5 (4) | 2 / 3 | 2.3 / 2.7 |
| thinking off + xhigh sentence | 2 (0) | 4 (1), 1 rule broken | 2 / 3 | 2.5 / 4.0 |
| **thinking at medium** | **7 (6)** | **7 (7)** | 3 / 3 | **4.4 / 4.1** |
| thinking at xhigh | 7 (2) | 7 (4) | 3 / 3 | 6.0 / 6.5 |
| xhigh, reminder off | 7 | 7 | -- | -- |

(xhigh, reminder off: the items that got the step-20 reminder at xhigh, run again without it; the others are carried
over from xhigh, and one per arm was re-run as a control and replayed exactly.)

## Predictions

| | result |
|---|---|
| M1 BASE at medium declares >= 5 of 7 | **holds**: 7 of 7, 6 before any reminder |
| M2 the read-every-file style goes away without the sentence (median calls before the first write on twins <= 6) | **fails**: 10 (BASE) and 8 (PIA); thinking off 2 to 5. Thinking at medium produces the style too |
| N1 BASE without the reminder declares >= 4 of 7 | **holds**: 7 of 7 |
| no false "impossible", nothing gamed (both cells) | holds: 0 and 0 |

## Cell N: the reminder was not doing the work

On every reminded item the no-reminder episode is **identical to the xhigh episode for its first 20 replies** (greedy
replay again), and the 21st reply differs, because one saw the reminder and the other did not. Yet the outcome did
not change: BASE declared at step 21 on four items exactly as with the reminder (K3 deep at 23 instead of 24); PIA at
21, 22 and 25 (21 on all three before). Both control items (never reminded at xhigh) replayed their whole episodes
byte for byte. At xhigh both models follow a regular course -- read every file, write, run the check, analyse --
that reaches its conclusion around step 21, right where the step-20 reminder lands. In `RESULT_SEED2.md` the
reminder looked like a cause; it was a coincidence of timing.

## The probe at medium

Control reproduced 14 of 14. Removing the earlier reasoning took away the declaration at **7 of 14** declaring steps,
added none; in all 7 the agent ran the checks again instead. With xhigh (`RESULT_SEED2.md`): 6 of 14. Together, 13 of
28 deciding steps depend on reasoning the model wrote earlier and reads back.

## Reading

1. **Thinking is the active ingredient.** Thinking off, the base declares 1 of 7; the injected sentence alone, 2;
   thinking with nothing injected, 7. The reminder is not needed at xhigh. Mark's hypothesis that the sentence
   carries xhigh's effect is not supported on this test; on the adapter the sentence without thinking even did harm.
2. **Medium beats xhigh here.** Same 7 of 7, but declared earlier and mostly unprompted (BASE 6 vs 2 before step 20),
   at 4.1-4.4 lane-hours against 6.0-6.5. It agrees with A6 (`viability/RESULT_A6_EFFORT_NOT_SAMPLING.md`), where
   xhigh was worse than medium at knowing when to stop on unanswerable factual questions.
3. **The working style comes from thinking or the sentence, either one.** Opening nearly every file before writing
   appeared with the sentence alone (9-11 calls), with thinking at medium (8-11) and at xhigh (10-13); thinking off it
   is 2-5. `RESULT_SENTENCE.md` attributed it to the sentence; that was half right.
4. **The adapter's edge belongs to the thinking-off setting.** With thinking at either effort both arms declare
   everything; the adapter's advantage is reaching most of it without thinking, in about two-thirds of medium's time.

## Limits

One seed, 7 impossible items per arm; at ceiling on the primary measure in every thinking cell, so differences
between thinking cells show only in timing and unprompted counts. The probe changes one step only.
