# Result — labels on the contact sheet moved a vision model's ranking; blind, it ranks differently and measures something our scorer cannot

**2026-09-11, exploratory and NOT pre-registered.** Two runs by Mark on `gemini.google.com`,
temporary chat, extended thinking. n = 15 drawings, one run per condition.

## The leak

`contact_sheet.png` was built as a lab artifact: every thumbnail is captioned with the **arm name,
the completion-token count, and our structural score** (`score_pelican3.py`, `contact_sheet()`). It
was then used as a stimulus for a model asked to grade the drawings. That is a leak of the answer
key.

**Direct evidence the text was read, not just the images:** both Gemini Pro 3.1 and Gemini Flash 3.8
referred to the second row as **"CWOPUS"**. The caption reads `QWOPUS`. A misread of `Q` as `C` is
only possible if the label was being read.

**The labeled ranking reproduces the printed scores exactly:**

| arm | printed structural scores | mean |
|---|---|---|
| DAVIDAU | 9, 10, 10, 10, 10 | **9.80** |
| BASE | 9, 10, 9, 10, 10 | 9.60 |
| QWOPUS | 6, 10, 10, 9, 10 | 9.00 |

Both models returned DAVIDAU > BASE > QWOPUS — one of six possible orderings, produced twice, with
those numbers legible in the image.

**The leak also propagates a known instrument artifact.** QWOPUS's 9.00 is dragged down by a single
6/10, and `RESULT_PELICAN3.md` establishes that this 6 is a scorer artifact (ground lines merging
the lower-band wheel clusters), not a defect a viewer would see.

## Blind re-run

`contact_sheet_blind.png`: identical 15 drawings, **no captions**, rows and columns shuffled, key
held back (`contact_sheet_blind_KEY.txt`). Prompt used Mark's capability rubric — *closest to a
correct pelican riding a bicycle; penalise incomplete frames, broken geometry, floating parts, bad
bird anatomy; do not penalise lack of charm or colour* — and asked for a per-image score.

| arm | **blind** | labeled Pro 3.1 | labeled Flash 3.8 | our scorer |
|---|---|---|---|---|
| BASE | **5.40** | 5.0 | 5.5 | 9.60 |
| DAVIDAU | 4.80 | 6.0 | 6.0 | 9.80 |
| QWOPUS | 4.60 | 4.0 | 4.8 | 9.00 |

- **The top two swapped.** DAVIDAU fell from first to second, and its absolute score fell furthest
  (6.0 → 4.80) — it was the arm the labels favoured most.
- **Position cannot explain the change.** The shuffle happened to return the identity permutation,
  so each arm occupied the same row in both runs (BASE row 1, QWOPUS row 2, DAVIDAU row 3). Whatever
  moved between the runs, it was not row position.
- **One run per condition.** Vision-model output is stochastic and no repeats were taken, so
  run-to-run noise is an unexcluded alternative to the label effect. **This does not establish the
  size of the leak, only that a leak existed and the ranking is not stable across it.**

## The two instruments do not measure the same thing

Spearman over the 15 drawings, blind Gemini score vs:

| against | rho |
|---|---|
| our structural score | **+0.04** |
| component count (fewer = less fragmented) | −0.24 |
| completion tokens | +0.21 |

**Effectively no relationship with our scorer.** They also differ in dynamic range: our scorer spans
9–10 on these drawings (saturated), the blind rubric spans 3–7.

**What the model can see that the probe cannot.** On QWOPUS r1 (blind score 3, the lowest) Gemini
wrote *"Disconnected front wheel and broken frame."* Re-probing the render shows the bird and the
bicycle are a **single connected component**; the other three components are the sun, a cloud, and
the ground lines (`QWOPUS_r1_components.png`). So the drawing is not literally disconnected, and
`RESULT_PELICAN3.md` stands.

The judgment is about **mechanical plausibility** — whether the frame reads as a bicycle that could
work, whether the fork attaches. `svg_probe.py` asks whether ink forms one blob with two lower
clusters; it has no vocabulary for "this is not a valid bicycle". Both instruments independently
ranked QWOPUS r1 worst, for unrelated reasons.

## Consequences

- **Never use `contact_sheet.png` as a stimulus.** It is captioned by design. `contact_sheet_blind.png`
  is the stimulus; the key stays out of the prompt.
- **A capability rubric produces discrimination where the mechanical scorer saturates** (range 4 vs
  range 1). That is the property a larger panel needs.
- **Arm is confounded with row** in the blind sheet: each row is still one arm, so any row-position
  bias maps onto an arm. A proper stimulus interleaves arms across the grid, or presents one drawing
  at a time.
- **Repeats are mandatory before any claim.** Self-consistency across runs is the machine equivalent
  of the repeated-pair check used on the human panel.

## What is not claimed

- Nothing about which model draws better pelicans. The blind run is a single pass over 15 drawings.
- Nothing about whether Pro 3.1 and Flash 3.8 share a vision encoder. Identical ordering under the
  labeled condition is equally explained by both reading the same captions.
- No pre-registration, so every number here is exploratory.
