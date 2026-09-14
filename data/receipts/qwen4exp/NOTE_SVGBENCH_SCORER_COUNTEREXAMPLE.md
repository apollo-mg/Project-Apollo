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
