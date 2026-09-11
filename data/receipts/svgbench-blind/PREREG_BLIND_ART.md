# Pre-registration — blind pairwise art judgement of the svgbench ladder drawings

**Registered 2026-09-10, with the predictions written before the page was built. No pick exists
yet.**
**Instrument:** `tools/svgbench/build_blind_page.py`, published as the page "Blind Pelican Judging".
**Rater:** Mark (n = 1).

## Why

The structural scorer saturated (`svgbench-ladder/RESULT_LADDER.md`): 7 of 10 first drawings scored
the maximum, so it cannot tell whether one sound drawing is a better picture than another. This asks
the one judge available, Mark's eye, under blinding, so his taste cannot favour a bit depth. He never
sees a label.

## Design

- **32 renders:** every drawing in `svgbench-ladder/` (10 first drawings, 22 corrections). Each is
  composited onto white exactly as the scorer saw it, re-encoded without metadata, and tagged with a
  random 4-character code.
- **75 comparisons,** one at a time, with two drawings side by side (stacked on a phone):
  - **45 first-drawing pairs:** every pairing of the 10 first drawings (6 Q2-class, 4 Q4-class).
  - **22 revision pairs:** each correction against its parent. intent2 and goal2 are compared with p1;
    goal3 is compared with goal2. That gives 10 intent and 12 goal pairs.
  - **8 repeats:** pairs drawn from the first 45 positions, shown again with the sides swapped, at least
    12 comparisons later.
- **Shuffling:** sides and order were shuffled once, from the OS RNG, at build time. The page never
  says which kind a pair is.
- **Question, verbatim:** *"Which is the better picture of a pelican riding a bicycle?"* The answers are
  A, B, or "Too close to call". Each pick can also be flagged "I know which quant made one of these".
- **The question is the goal arm's own instruction, word for word.** P-B4 therefore partly tests whether
  goal framing achieved its stated aim. This is disclosed, and intended.

## Blinding

- **No labels in the page.** It holds no quant, rep or step labels. The only map from code to drawing
  is `MAPPING_SEALED.json`, which stays out of git until Mark says he is done. Its SHA-256 is recorded
  below, so it cannot be changed afterwards without detection.
- **I will not read the picks until Mark says he has finished.**
- **Known leak:** Mark saw at least one render during the run (the colourful one with a cloud and a
  sun) and may remember others. Picks flagged "I know which quant made one of these" are excluded from the
  primary analyses and reported separately.
- **Flag reworded before any pick.** It first read "I've seen one of these before". After the first
  few pairs every pair would qualify, since each first drawing appears in nine pairs. Blinding only
  needs to know whether the label is known, so that is what it now asks.

## Analysis (fixed now)

1. **Art ranking of first drawings.** Each first drawing's score is its win rate over the
   first-drawing pairs it appears in, with "too close" counting half.
   - **Statistic:** of the 24 Q2-vs-Q4 pairings, the number in which the Q4 drawing has the higher
     score (equal scores count 0.5).
   - **Test:** an exact permutation test over all 210 ways to assign the 4 Q4 labels to the 10
     drawings; two-sided, α = 0.05.
   - With no ties this is the rule from the ladder discussion: 22 of 24 are needed.
2. **Did revision help?** How often the child is preferred over its parent among the 22 revision
   pairs, excluding ties. Exact two-sided sign test.
3. **Framing.** The child-preferred rate for intent (10 pairs) vs goal (12 pairs). Fisher exact,
   two-sided. At this n it is descriptive.
4. **Consistency.** A repeat agrees if the same drawing wins both times; "too close" both times also
   counts as agreement. Reported as k of 8.
5. **Descriptive only:** Mark's revision preferences, set against the structural score changes and
   against the exploratory change magnitude.

**Rules pinned before any pick (added after review, before the link was sent):**
- **Repeated pairs.** A repeated first-drawing pair enters the win rate once, at the mean of its two
  judgments (win 1, too close 0.5, loss 0, after un-swapping the sides). A pair judged one way and
  then the other therefore enters as 0.5. Both judgments are used for P-B5.
- **Flagged judgments.** A judgment flagged "I know which quant made one of these" is dropped. If both
  judgments of a repeated pair are flagged, the pair is dropped.
- **Changed picks.** The page overwrites a changed pick. The last pick counts, and its stored `at`
  timestamp records when it was made.
- **Stopping.** The analysis runs once, when Mark says he is done, with no interim looks.
  Each prediction needs a minimum number of usable judgments; below it, the prediction is reported
  NOT EVALUABLE (incomplete), with its numbers descriptive only:

  | prediction | minimum usable |
  |---|---|
  | P-B1, P-B2 | 40 of the 45 first-drawing pairs |
  | P-B3, P-B4 | 18 of the 22 revision pairs |
  | P-B5 | 6 of the 8 repeats |

## Predictions (logged before the page was built)

| id | prediction | conf |
|---|---|---|
| P-B1 | Mark's ranking does **not** separate Q2 from Q4 first drawings (permutation p ≥ 0.05) | 70% |
| P-B2 | Direction only: the Q4 drawing wins more than 12 of the 24 Q2-vs-Q4 pairings | 55% |
| P-B3 | The child is preferred over its parent in more than half of the non-tie revision pairs | 65% |
| P-B4 | Goal-framed children are preferred over their parents at a higher rate than intent-framed children | 50% |
| P-B5 | At least 6 of the 8 repeats agree | 70% |

## What will not be claimed

- **No general claim about bit depth.** Nothing beyond this prompt, this model and this rater:
  one rater, and 6 v 4 first drawings.
- **No general claim about art quality.** The picks are one person's blind preferences, which is
  exactly what they are meant to be.

## Sealed mapping

`MAPPING_SEALED.json` SHA-256: `cd1d4f46a6b160ab45461f1875e2f4e2bd187838153551c1a978bb03158764e9`

The mapping was built from the OS RNG before any pick existed. It is kept out of git by the last
line of `.gitignore` until Mark says he is done. `.git/info/exclude` was tried first and does not
work in this repo, because `.gitignore`'s `!data/receipts/**` overrides it.

**Noted at build, before any pick: all 8 repeats fell on first-drawing pairs.**
- **Not a shuffle fault.** The first 45 positions held 30 first-drawing and 15 revision pairs, which
  makes this a ~3% draw (C(30,8)/C(45,8)).
- **Kept, not reshuffled.** Re-drawing until the randomisation looks nicer is itself a selection.
- **Consequence:** P-B5 measures consistency on first-drawing pairs only, which are the comparisons
  P-B1 rests on.

**Checked at build.**
- Outside the embedded image data, the page contains no quant, rep, step or pair-kind strings. The
  only hit was `e.repeat` in the key handler.
- The 12 `IQ2`/`IQ4` hits all fall inside the base64 image data.

## Addendum 2026-09-11 — outside raters (logged before any outside pick exists)

Mark will invite one or two people from Discord. They rate on a separate page, "Pelican Judging
Panel" (`tools/svgbench/build_share_page.py`). It is built from the same sealed mapping: the same 32
renders, codes and 75 pairs, in the same order.

**What differs from Mark's page.**
- **Storage:** progress stays in the rater's own browser. Results leave the page only when the rater
  copies them to Mark.
- **Sides:** each rater gets random left/right flips. They are keyed so that a repeat still appears
  swapped relative to its original.
- **Recording:** a pick is recorded as the winning drawing's code.
- **Flag:** it reads "I've seen one of these outside this page", because an outside rater cannot know
  which quant drew anything.

**Mark's analysis is unchanged.** P-B1..P-B5 are his, scored exactly as registered above.

**Outside raters form a separate, secondary analysis.**
1. Each rater's own P-B1..P-B5, under the same rules and completion minimums.
2. **Agreement with Mark.** On pairs both judged decisively (no tie, no flag), the fraction where
   they picked the same drawing. Reported per rater, with the pair count.
3. **Pooled first-drawing scores.** Each drawing's win rate is averaged across all raters with at
   least 40 usable first-drawing pairs, then put through the same permutation test as P-B1. This is
   secondary; it does not replace Mark's P-B1.

**Exclusions, fixed now.**
- A rater whose exported median decision time is under 1.5 s is treated as clicking through, and
  excluded.
- Results count only if they arrive as the page's exported text. Nothing is transcribed by hand.

**Power, stated plainly.** More raters make each drawing's score more reliable; they do not add
drawings. The bit-depth comparison stays 6 v 4, and its best possible p stays about 0.01.

| id | prediction | conf |
|---|---|---|
| P-B6 | Each outside rater agrees with Mark on more than 60% of decisive first-drawing pairs | 55% |
| P-B7 | The pooled ranking does not separate Q2 from Q4 either (p ≥ 0.05) | 75% |
