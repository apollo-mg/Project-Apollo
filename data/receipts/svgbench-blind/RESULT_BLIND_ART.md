# Result — blind judging: Mark's eye leaned 4-bit, just short of the line; a second rater saw no lean

**Date:** 2026-09-11.
- **Prereg:** `PREREG_BLIND_ART.md` and its two addenda, all committed before any pick was read.
- **Data:** `picks_mark/` (75 picks, exported to files without being viewed) and `raters/R1_export.txt`
  (verbatim).
- **Mapping:** unsealed at `9bbabf3`, after its hash matched the prereg.
- **Scorer:** `tools/svgbench/score_blind.py`, committed before it ran once. Output is in
  `score_output.txt`.
- **Descriptive extras:** `tools/svgbench/blind_leak_sensitivity.py`.

## Headline

- **Bit depth, judged on the picture: no separation at the pre-registered line, but only just.**
  Mark put the 4-bit drawing ahead in 21 of 24 cross pairings; the exact permutation p is 0.057
  against α = 0.05. P-B1 (no separation) is CONFIRMED, and P-B2 (direction favours 4-bit) is
  CONFIRMED.
- **The second rater saw no lean at all:** 12.5 of 24, p = 0.96. The two rankings barely correlate
  (Spearman +0.28, n = 10), and they disagree most about Mark's favourite drawing.
- **Mark's judgments are reliable.** All 8 repeats agreed, with the sides swapped.
- **Most corrections didn't change the picture enough to matter.** Mark called 15 of the 22
  before/after pairs too close to call. When he did decide, the correction won 6 of 7 (sign test
  p = 0.125). R1: 10 of 14.
- **Both raters, blind, preferred all four corrections the ladder receipt singled out** before
  anyone rated: both wing-on-the-handlebars fixes, the neck outline, and the step that diagnosed the
  dangling foot. Each was preferred over its parent by both raters.
- **Goal vs intent framing: no difference** for either rater at this n.

## Mark — primary, exactly as pre-registered

| | prediction | conf | verdict |
|---|---|---|---|
| P-B1 | Q2 and Q4 first drawings do not separate (p ≥ 0.05) | 70% | **CONFIRMED** — 21/24, p = 0.057 |
| P-B2 | direction: 4-bit ahead in more than 12 of 24 | 55% | **CONFIRMED** — 21 |
| P-B3 | child preferred in more than half of decisive revision pairs | 65% | **CONFIRMED** — 6/7 (15 ties), sign p = 0.125 |
| P-B4 | goal children preferred at a higher rate than intent children | 50% | **FALSIFIED** — goal 4/5 vs intent 2/2, Fisher p = 1.0 |
| P-B5 | at least 6 of 8 repeats agree | 70% | **CONFIRMED** — 8/8 |

Mark made 75/75 picks, with no flags, a median of 9.3 s per pair, and 47 decisive picks.

## First-drawing win rates, labels unsealed

| code | drawing | Mark | R1 |
|---|---|---|---|
| UVR7 | UD-Q4_K_M r1 | 0.944 | 0.111 |
| XJXK | UD-IQ4_XS r3 | 0.889 | 1.000 |
| KDLR | UD-IQ4_XS r1 | 0.722 | 0.722 |
| UHK9 | UD-IQ2_M r3 | 0.611 | 0.389 |
| X4RX | UD-Q2_K_XL r3 | 0.500 | 0.722 |
| YP4K | UD-IQ2_M r1 | 0.500 | 0.889 |
| XAA7 | UD-IQ4_XS r2 | 0.444 | 0.222 |
| DRYR | UD-IQ2_M r2 | 0.167 | 0.056 |
| FRWF | UD-Q2_K_XL r2 | 0.111 | 0.556 |
| XJMT | UD-Q2_K_XL r1 | 0.111 | 0.333 |

- **XAA7** is the drawing whose white neck vanished on the white canvas, the ladder's only real
  structural failure.
- **DRYR scored 6/10 purely through scorer artifacts,** and I called it "visually a sound pelican on
  a bicycle". Both raters put it last or next to last. Structurally sound is not the same as a good
  picture.

## The leak, scoped

**What could have been seen.** Before the blind page existed, six of the ten first drawings were
displayed in this session, through my own image reads, with the quant in the file name: Q2_K_XL r1
and r2, IQ2_M r1 and r2, and IQ4_XS r1 and r2. If Mark's app shows those reads, he could have seen
them labelled. He flagged none of his picks.

**Which drawing he described.** During the run he described one with "color, cloud, and sun". That
came nine minutes after a view of IQ4_XS r1 (KDLR), which has a sky, clouds, a sun and grass. My
first guess was UVR7, but UVR7 was never displayed in this session, so that guess was wrong.

**Descriptive, not pre-registered:**
- **Without KDLR,** the lean is 15.5 of 18, p = 0.095.
- **Among the four drawings never displayed,** the two 4-bit ones are Mark's top two (4 of 4; too
  few drawings for a test).
- **So the lean does not depend on the drawings he could have seen labelled,** though it is not
  significant either way.

## Outside rater R1 — secondary

- **Integrity:** 75/75 picks, integrity clean, median 2.9 s per pair (the click-through line is 1.5
  s), 66 decisive picks.
- **Human or agent: unconfirmed.** Addendum 2 applies, so everything below is reported both ways.
- **R1's own predictions:**
  - P-B1 CONFIRMED (12.5/24, p = 0.957).
  - P-B2 CONFIRMED on a coin flip (12.5 > 12).
  - P-B3 CONFIRMED (10/14, p = 0.18).
  - P-B4 FALSIFIED (goal 5/8 vs intent 5/6).
  - P-B5 CONFIRMED (7/8).
- **P-B6, agreement with Mark** on decisive first-drawing pairs: 21 of 32 = 0.66. CONFIRMED if R1 is
  a person.
- **P-B7, pooled ranking** (Mark + R1): 18 of 24, p = 0.257. CONFIRMED if R1 is a person; NOT
  EVALUABLE if not, because there would be only one eligible rater.

## Descriptive

- **Side preference:** Mark picked the left drawing in 25 of 47 decisive picks, and R1 in 36 of 66.
  Neither shows a strong side preference.
- **Big changes weren't reliably better.** Mark called all three of the largest corrections too
  close; R1 split them 2 to 1:

  | correction | change | Mark | R1 |
  |---|---|---|---|
  | goal2 on IQ2_M r3 | 0.776 | too close | child |
  | intent2 on Q2_K_XL r3 | 0.716 | too close | child |
  | goal2 on Q2_K_XL r2 | 0.697 | too close | parent |
- **The four singled-out corrections** were listed in `svgbench-ladder/RESULT_LADDER.md`, committed
  the day before the blind page existed:
  - IQ4_XS r1 `intent2`: the wing-arm
  - IQ2_M r2 `goal3`: the wing on the bars
  - IQ4_XS r2 `intent2`: the neck outline
  - Q2_K_XL r2 `goal3`: the dangling-foot step

  Both raters chose the child in all four. This was not a registered prediction, but the selection
  predates the ratings.

## Caveats

- **Sample:** one primary rater and ten first drawings (6 v 4). The test's best possible p is 0.01.
- **What is registered:** scoring follows the prereg. The leak sensitivity, the four-corrections
  observation and everything under Descriptive are not pre-registered.
- **R1:** R1's status is unconfirmed, and R1 is identified by handle in the raw export. That should be
  redacted before anything is published, unless he agrees.

## For the Q6 question

Blind, one person's eye leaned 4-bit, though not past the pre-registered line, and a second person
saw no lean at all. The structural result was that 2-bit first drawings are as sound as 4-bit.
Together, there is still no evidence that 2-bit costs this model anything on this task that holds up
across two raters. There is a hint, from one rater, that it might cost some polish. That hint is what
a larger set of fresh drawings would test.
