# svgbench v2 — requirements written by v1's failures

Every item below is a failure v1 actually produced on 2026-09-10, not a hypothetical.

## Measurement defects

1. **Backdrop shapes that don't touch the canvas edge count as ink.** A grass ellipse's curved tips and a
   ground-shadow ellipse both register as drawn content. Row/column edge colours are not a sufficient
   backdrop model; large low-detail bands in the bottom of the frame need handling as ground.
2. **4-connectivity at 4× downsampling breaks thin diagonal strokes.** Necks and legs drawn as 1–2 px
   diagonals fall apart into pieces, so a correctly attached head reads as detached. Use 8-connectivity
   and a finer grid for connectivity.
3. **Fills matching the backdrop isolate interior detail.** A white body on white leaves its wing as an
   island. Pixels enclosed by an ink contour should belong to the enclosing object (hole filling).
4. **Column-projection wheel detection is fragile.** It merges wheels with the frame, crank and shadows.
   Detect wheels as roughly circular ring components instead.

## What v1 cannot see at all

5. **Functional relations** — foot on a pedal, hand/wing on the handlebar, rider on the saddle, head joined
   by a neck. The model diagnosed and repaired several of these ("near leg dangles in mid-air… no pedal
   beneath it", "no wings on the handlebars") while the score stayed flat. These need part identification:
   a **fixed, versioned judge answering structured yes/no questions**, held constant across every model
   under test, or a DOM-level parse with transform resolution.
6. **Ceiling.** Competent models max the 10-check scorer on the first draw (4 of the first 6 first drawings).
   Needs graded scoring and/or harder prompts — Castillo's animal×vehicle grid supplies harder cells than
   pelican×bicycle.

## Design lesson

7. **The model's own fault lists are currently a richer signal than the scorer.** Two semantic faults found
   and fixed from a 64×30 text grid, both invisible to the score. v2's primary metric should measure
   whether a revision moved toward the goal on the relations the model can reason about — pre-registered
   this time, with change magnitude (exploratory in v1) as a candidate.
8. **Validate on the distribution the instrument will see.** v1 was validated on three plain-backdrop SVGs
   and broke on the first real drawing. v2 gets its calibration set from v1's saved outputs.
