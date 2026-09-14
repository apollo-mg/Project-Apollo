# Note — the v1 svgbench scorer never rewards a revision, and twice punishes one

**2026-09-14 10:38–10:50, `.194`**, Flash-Next UD-IQ4_XS `-ncmoe 2`, buun `c7f114d34`. Three pass-1
drawings from the informal run (`pelican_informal/`) put through **the real svgbench pass-2 scaffold** —
`run_ladder.py`'s own `scaffold()` text with the `goal` clause, grids from `svg_probe.py` at the committed
64×30. Scored with `svg_probe.py`, unchanged.

**This is not a panel arm** and the numbers below are not comparable to BASE/QWOPUS/DAVIDAU — see Limits.
**The finding is about the instrument, not about Flash-Next**, which is why it is worth recording.

## The result

| rep | pass 1 | pass 2 | checks lost on revision |
|---|---|---|---|
| 1 | **10/10** | **7/10** | `two_lower_clusters`, `clusters_separated`, `structure_between` |
| 2 | **10/10** | **9/10** | `assembly_coherent` |
| 3 | **10/10** | **10/10** | — |

**No revision scored higher than its original. Two scored lower. All three are visibly better** — each
fixed the defects a human names immediately (missing pouch, bird not seated, wings not on the bars).

**Rep 1 is the sharp counterexample.** Its revision gave the bird a proper gular pouch, scaled it to the
frame and put a wing on the handlebar — and lost 3 points because the larger bird bridges the two wheels,
collapsing `lower_band_clusters` from **8 to 1**. **The scorer penalised the drawing for having its parts
properly joined**, which is the defining property of a pelican *riding* a bicycle. That is V2 note #4
(*"column-projection wheel detection is fragile… merges wheels with the frame"*) reproduced on a real pair.

## Three distinct failure modes in the pass-2 loop, not one

The model's fault lists are a **richer** signal than the score, as V2 argued — and also an **unreliable**
one, in two different ways that should not be conflated:

1. **Rep 1 — the fault list is right and the scorer is wrong.** It named the missing beak/pouch, stiff
   legs and wings not reaching the bars. All real, all invisible to a 10/10.
2. **Rep 2 — the fault list is wrong.** It asserted *"the pelican is facing left while the bicycle faces
   right."* In the grid the beak sits clearly right of the neck column and the handlebar extends right;
   bird and bike both face right. A confident, specific, checkable claim about a defect that is not there.
   It also called the bird *too small* where it is visibly too large.
3. **Rep 3 — the fault list is right about the grid and wrong about the drawing.** It called the wheels
   *"just gone"*. They are in the SVG, drawn with thin strokes, and at 64×30 they survive only as broken
   fragments (`-+   :. --#:  =#=+#+**.`) beside the bird's solid `@@@`. **The representation deleted the
   bicycle and the model reported that faithfully.** V2 note #2 (thin strokes break under downsampling),
   with a consequence worse than a scoring artifact: the critique step is being run on a view that has
   silently dropped the subject.

**And the revision helps even when the diagnosis is wrong.** Rep 2 improved substantially despite the false
orientation claim, and rep 3's fix for its phantom missing wheels — drawing them bolder — made them
genuinely more legible in both the grid and the image. **So "did the revision improve?" and "was the
fault list correct?" are separate questions, and v2 should not assume the second implies the first.**

## What this gives v2

A **concrete acceptance test** rather than a design principle. The six SVGs are on disk in
`pelican_informal/`:

> **Any replacement scorer must rank `repN_goal2` above `repN` for N = 1, 2, 3.**

A candidate that cannot clear that bar is not measuring what a human reader measures. Rep 1 is the
strictest case (10 → 7 under v1) and rep 3 the weakest (10 → 10).

It also argues for the **fixed versioned judge answering structured yes/no questions** that V2 already
proposes, over "grade the model's own fault list": modes 2 and 3 above are failure modes a judge does not
inherit, because the judge sees the render rather than the model's account of it. **And whatever the judge
sees should not be the 64×30 grid** — mode 3 is an argument for giving it more than the density map.

## Limits

- **n = 3, one model, one prompt, one framing** (`goal` only; the panel also runs `intent`). A counterexample,
  not a rate. "Visibly better" is my judgement, not a blind rating.
- **Not comparable to panel arms.** This run used **thinking off** (`enable_thinking: false`) where the panel
  runs `--reasoning-effort medium` with thinking on, `-ctk/-ctv q8_0` where this used f16, `-c 24576` where
  this used 8192, and an RX 9070 XT where this used four P100s. **It cannot be scored beside BASE, QWOPUS or
  DAVIDAU**, and nothing here should be read as a quality claim about Flash-Next.
- **The pass-1 drawings all scored 10/10**, so this says nothing about how v1 behaves below its ceiling.
- The rep-2 orientation reading is mine, from the grid and the render; I did not instrument it.

Artifacts: `pelican_informal/` — `repN.svg`, `repN_goal2.svg`, renders, `repN_goal2.content.txt` (full fault
lists), `run.log`.

---

## Amendment 1 — 2026-09-14 11:45: **the headline was arm-specific and is corrected**

The matched re-run (`pelican_matched/`, `--reasoning-effort medium`, thinking **on**, everything else as the
panel sets it) completes the 2×2. **The claim above — "never rewards a revision, twice punishes one" — holds
only for the thinking-OFF arm.**

| arm | rep 1 | rep 2 | rep 3 | revisions |
|---|---|---|---|---|
| **thinking OFF** | 10 → **7** | 10 → **9** | 10 → 10 | **2 down, 1 flat, 0 up** |
| **thinking ON** | 10 → 10 | **9 → 10** | **9 → 10** | **0 down, 1 flat, 2 up** |

**A clean reversal.** With thinking on, revisions hold or improve. The earlier headline was true of the data
it was written on and false as a general statement about the scorer; it is corrected here rather than edited
away.

**Likely reason, not measured:** the thinking-off revisions made bold structural changes — scale the bird up,
merge it into the frame — which is exactly what trips the connectivity checks. The thinking-on revisions are
more surgical, fixing named relations without redrawing the composition. If that is right, the scorer is not
"anti-revision" but **anti-large-structural-change**, which is a narrower and more accurate charge.

### What survives unchanged, and is the stronger result

**The ceiling and the two broken checks.** Across all **twelve** drawings the scores are 7, 9 × 3, and 10 × 8
— the instrument has almost no dynamic range — and **every one of the four non-perfect scores comes from just
two checks**:

- `assembly_coherent` (3 of 4). **Demonstrably broken** — see `pelican_matched/SUN_REPRO.md`: deleting one
  decorative `<circle>` (the sun) moves a drawing from 9/10 to 10/10, and the defect is *conditional on the
  rest being well-drawn*, because the fragment threshold is relative to the main component.
- `two_lower_clusters` / `clusters_separated` / `structure_between` (the remaining 1, all three at once).
  Wheel detection collapses when the bird bridges the wheels — V2 note #4.

**Neither depends on which arm produced the drawing.** The sun repro is the artifact to hand a v2 candidate,
precisely because it is a one-element diff rather than a judgement call about which of two pictures is better.

### Answering the question the re-run was for

**Thinking on produces visibly better first drawings and the scorer cannot see it.** Thinking-on rep 1 pass 1
is the best first draw of the session — pouched beak *and* a correct bicycle *and* a saddle the bird sits on —
and scores 10/10, the same as a thinking-off draw with a goose-like head and no pouch. Two thinking-on first
draws score **9**, *below* the thinking-off drawings they beat, both on the sun defect.

Cost: 10,181 output tokens across three reps against 8,719 with thinking off (**+17%**), plus reasoning blocks
of 3,668 / 2,315 / 2,809 chars where thinking-off produced none.

**An observation worth controlling for in v2, n=3 and untested:** thinking-on pass 1 looks comparable in
quality to thinking-off pass 2. If the reasoning block buys roughly what the render-feedback loop buys, then
the panel — which gives pass 1 a thinking budget — is not cleanly isolating *seeing the render* from *thinking
longer*. The control is a token-matched arm: thinking-off pass 1 + revision, against thinking-on pass 1 alone.

### Limits on this amendment

- Still n=3 per arm, one model, one prompt, `goal` framing only.
- "Visibly better" remains my judgement, not a blind rating.
- **Still not a panel arm**: four P100s not an RX 9070 XT, `c7f114d34` not `3823c9eb6`, `max_tokens` 8000
  approximating the panel's 480 s cap, and `-lv 4` added so the KV assertion could fail.
- **The KV is mixed, not q8_0.** `-ctk/-ctv q8_0` on this hybrid architecture logs `K (f16) K (q8_0) V (f16)
  V (q8_0)` — the attention cache quantizes, the recurrent state stays f16. The panel's dense 27B has no such
  split, so "matched KV flags" is true of the flags and only partly true of the cache.
