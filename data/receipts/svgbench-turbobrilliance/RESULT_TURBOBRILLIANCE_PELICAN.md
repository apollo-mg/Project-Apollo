# RESULT: DavidAU's Turbo-Brilliance modes on the pelican: recognisable, not preferred, and the cost is in the answer

**Date:** 2026-10-12. **Prereg:** `PREREG_TURBOBRILLIANCE_PELICAN.md` (commit `0b80c920`, before any generation),
Deviation 1 (`04e5d256`, streaming client, after rep 1), Addendum 1 (`ce952e06`, page sealed, before any rating).
**Model:** pelican3's Qwen3.8-27B i1-IQ3_M with DavidAU's template pinned (`cbb40c02`, sha256 `e5b21666`), stock
weights, so this tests the template and nothing else. 5 reps per arm, CTRL / CODER / QUINN / OMNI.

## Headline

1. **Mark could tell which picture came from a mode almost every time: 11 of 12 decisive guesses right**
   (one-sided p = 0.003). That includes 4 of 5 on pairs where the control drawing was new to him, so the
   recurrence tell does not explain all of it.
2. **He still did not prefer the mode pictures. Mode 3, control 6** (4 shown control wins plus the 2 OMNI pairs
   with no drawing), 6 "can't decide". Sign test p = 0.51. Each mode lands 1 win, 2 losses, 2 ties.
3. **The extra tokens go into the answer, not the thinking.** Mode answers run about 2x control (median 8.7k vs
   4.4k chars; SVGs 7.6-8.6 KB vs 4.0 KB), while median reasoning is no longer (CODER 5.3k, QUINN 3.8k, OMNI 4.3k vs
   control 5.8k chars). Median completion tokens rise 6-31%, and none of the three reaches p < 0.05.
4. **The personas live in the answer text. The reasoning stays generic planning in all three modes.** Every mode
   trace opens with the same "The user wants…" / "is asking…" planning as control. QUINN's reasoning names Harley Quinn in the third
   person ("I need to stay in character") but plans the drawing plainly. Then every QUINN answer opens in
   character with an emoji and a stage direction. OMNI's five required DIMENSION headings appear in 1 of 4
   traces; another (r4) notes the task does not need them. CODER's listed vocabulary appears nowhere.

## Primary outcome: blind preference (H-1)

`score_panel.py` (registered scoring, checks the mapping against the sealed sha256 before reading it) over
`ratings_mark.json`. Output in `panel_score.json`.

| | mode | control | can't decide |
|---|---|---|---|
| CODER (5 pairs) | 1 | 2 | 2 |
| QUINN (5 pairs) | 1 | 2 | 2 |
| OMNI (3 shown + 2 unshown) | 1 | 2 (both unshown) | 2 |
| **Pooled, 15 pairs** | **3** | **6** | **6 excluded** |

**Exact two-sided sign test, 3 v 6: p = 0.508. H-1 held.** Mark is the only rater so far. Outside raters can
still be pooled under the prereg's rule (they confirm no AI assistance). Per mode is descriptive by
registration (5 pairs cannot reach p < 0.05).

**Both OMNI losses are the unshown pairs.** Among OMNI's 3 shown pairs Mark picked OMNI once (r4) and could not
decide twice. That r4 drawing has the pelican's wing reaching forward to grip the handlebar, and it scored 7/10
on the structural probe.

**Six "can't decide" in 13 shown pairs** says the drawings are close. Mark took a median 30 s per pair (p01
excluded: its timer ran ~10 h because the page sat open overnight).

**Mode SVGs are about 2x the bytes of control, and that did not buy preference.** This contrasts with
`svgbench-blind/RESULT_COMPLEXITY_CONFOUND.md`, where the favoured 4-bit drawings were also the more complex
ones. Here the more complex side lost 3 v 6.

## The persona guess (H-3, the leak measure)

| pairs | control drawing | right / decisive |
|---|---|---|
| p01-p05 | first appearance (no recurrence tell possible) | 4 / 5 |
| p06-p13 | already seen in an earlier pair | 7 / 7 |
| all | | **11 / 12** (1 "no idea") |

**H-3 held, strongly.** Addendum 1 logged three tells:

- **Recurrence:** a drawing seen before is control.
- **Text:** QUINN r3 "vwoop" (p13), QUINN r4 "whoosh~" (p02). Both were guessed right.
- **Size/detail:** mode SVGs carry more detail.

The page's random order happened to put every control drawing's first appearance in p01-p05. That split gives
a clean read on style alone: 4 of 5, which is suggestive and not significant on its own (one-sided p = 0.19).

**The guess did not drive the preference.** In decisive pairs, Mark preferred the side he guessed was the
persona in 4 of 7.

## Cost (secondary, registered; H-4 to H-8)

Completion tokens. Capped reps rank above every completed rep (R1).

| arm | r1 | r2 | r3 | r4 | r5 | median | Mann-Whitney vs CTRL |
|---|---|---|---|---|---|---|---|
| CTRL | 5,022 | 5,055 | 6,414 | 3,847 | 3,715 | 5,022 | |
| CODER | 5,510 | 5,475 | 11,368 | 5,953 | 9,702 | 5,953 | U = 22, p = 0.056 |
| QUINN | 5,841 | 5,173 | 4,465 | 5,345 | 7,811 | 5,345 | U = 19, p = 0.222 |
| OMNI | cap | cap | 5,039 | 6,590 | 6,157 | 6,590 | U = 22, p = 0.056 |

- **Prompt overhead per request:** CODER +2,701 tokens, QUINN +2,624, OMNI +948 (CTRL prompt 21 tokens).
- **Median elapsed:** CTRL 179 s, CODER 220 s, QUINN 198 s, OMNI 225 s (completed reps), plus two at the 480 s cap.
- **OMNI runaways were slow, not looping.** When cut off, OMNI r2 had 19.5k chars of reasoning and 8.3k chars of
  answer, and was mid-SVG. Rep 1 predates the streaming client, so only its counts survive.

| arm | median reasoning chars | median answer chars | median SVG bytes |
|---|---|---|---|
| CTRL | 5,764 | 4,388 | 3,988 |
| CODER | 5,310 | 8,755 | 7,712 |
| QUINN | 3,805 | 8,679 | 7,561 |
| OMNI (3 completed) | 4,328 | 8,631 | 8,620 |

## What the reasoning looks like per mode (Mark's question; reps 2-5)

`reasoning_compare.py` produces `reasoning_compare.json`. Its counts are mine, chosen after the run, so they are
descriptive.

- **CTRL:** generic planning, coordinates, few self-corrections (0-0.55 revisions per 1k chars).
- **CODER:** the reasoning never mentions the persona (0 hits in 4 traces) and opens like control. It has one
  measurable difference: a self-revision rate of 0.90-1.13 per 1k chars, above every control trace (exploratory
  exact Mann-Whitney 4 v 4, p = 0.029). The CODER block's "Talks like" line lists "self-correction markers" among
  its rhetorical devices. The persona shows mainly in the answer: about 1.7-4x control's prose, as architecture notes and
  tables. One answer is titled "DevOracle — Delivery Summary".
- **QUINN:** all 4 traces name the persona in the third person, as a constraint on the answer ("stay in
  character as Harley Quinn"), then plan the drawing in a neutral voice. The shortest trace in the campaign is
  QUINN r3, at 1,264 chars. Every QUINN answer opens in character with an emoji and a stage direction.
- **OMNI:**
  - r5 walks DIMENSION 1-5, applying the five headings literally to the drawing (layering order as an
    "adversarial vulnerability").
  - r4 says the request is "not really a 'problem' that needs the full 5-dimensional adversarial analysis",
    then plans normally.
  - r3 and the capped r2 ignore the scaffold.
  - No OMNI answer carries the headings. Two OMNI answers are nothing but the SVG.

**Reading:** on this task the modes change what the model writes out, not how it reasons. The reasoning is
the same planning with a different label on top, and the persona appears as voice and packaging in the answer.

## Predictions

| id | prediction | conf | outcome |
|---|---|---|---|
| H-1 | pooled sign test not significant | 60% | **held** (3 v 6, p = 0.51) |
| H-2 | Mark favours the mode side in at most 9 of 15 | 60% | **held** (3) |
| H-3 | Mark's persona guesses above half | 55% | **held** (11/12) |
| H-4 | OMNI tokens > CTRL, p < 0.05 | 60% | **false** (p = 0.056) |
| H-5 | CODER tokens > CTRL, p < 0.05 | 50% | **false** (p = 0.056) |
| H-6 | QUINN tokens > CTRL, p < 0.05 | 40% | **false** (p = 0.22) |
| H-7 | no CTRL rep hits the cap | 85% | **held** |
| H-8 | at least one mode rep hits the cap | 35% | **held** (OMNI r1, r2) |
| H-9 | all 20 drawings 10/10 or known artifacts | 45% | **false** (2 drawings missing) |

**H-9 detail:** the three sub-10 drawings all look sound when rendered. This is my judgement under the
`svgbench-ladder/RUN_NOTES.md` rule, and it is disclosed as such.

- **QUINN r3 (7/10) and OMNI r4 (7/10):** each has a ground ellipse under the bike that joins the lower band
  into one run. That is the IQ2_M r2 wheel-check artifact.
- **QUINN r1 (9/10, `subject_attached`):** the near-white body on a pale backdrop drops out of the ink mask
  (see `QUINN_r1_p1.grid.txt`), leaving the head and pouch apparently afloat. The body is visibly outlined and
  seated, with the legs on the pedals. That makes it the same mechanism as the ladder's "wing inside a visibly
  outlined body".

## What this adds to prior art

The earlier DavidAU receipts (`svgbench-pelican3`, the Twin-Turbo rows in INDEX) measured DavidAU's *tune*, whose
weights think less than stock. This campaign holds the weights fixed and switches only the template. On this task
the modes neither raise reasoning nor improve the picture. They roughly double the answer and add 1-2.7k prompt
tokens per request. And they are visible enough that a rater can pick them out.

## Limitations

- **One rater.** The sign test covers Mark's eye only.
- **Renders only, not the answer text.** The page showed pictures. The modes' clearest effect, the voice and
  packaging of the answer, was never rated. That is the UX question Mark raised before the run ("maybe the
  experience … feels subjectively better or different"), and this panel does not answer it.
- **IQ3_M rather than MAX; one task; n = 5.** CTRL ran at the template's `medium` default (no injected effort
  text).
- **The reasoning metrics were chosen after reading the traces.** They are descriptive. The CODER revision-rate
  difference is a lead, not a finding.

## Files

- **Ratings and scoring:**
  - `ratings_mark.json`: picks as saved by the page, account id omitted.
  - `score_panel.py` produces `panel_score.json`.
  - `MAPPING_SEALED.json`: sha256 `d77a2f10…`, verified by the scorer.
  - `blind_page.html`
- **Per rep:**
  - `<ARM>_r<k>_p1.{svg,png,content.txt,grid.txt}`
  - `.reasoning.txt` for reps 2-5
  - `OMNI_r2_p1.partial_*`
  - `prompt_*.txt`, `server_*.log`, `results.jsonl`, `memtrace.csv`
- **Reasoning comparison:** `reasoning_compare.py` produces `reasoning_compare.json`.
