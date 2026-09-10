# svgbench — iterative drawing benchmark instrument

Built to replace the one-shot "duck riding a bicycle" test, which measures a single draw from a
distribution with no feedback. This measures three separable things instead:

- **first-pass prior** — the classic one-shot score
- **feedback utilization** — improvement per iteration, the number nobody publishes
- **convergence** — does it plateau, oscillate, or degrade

## Two scores, never blended

**Engineering (mechanistic).** `svg_probe.py structural()` — deterministic binary checks off the
*render*, so a wheel drawn as a `<path>` counts the same as one drawn as `<circle>`. No model, no
judge. Currently 9 checks: renders, non_blank, canvas_use, two_lower_clusters,
clusters_similar_width, clusters_separated, structure_between, mass_above, colour_variety.

**Art (judged).** Separate, subjective, scored by a *fixed* judge asking structured yes/no
questions. Held constant across every model under test, so it is a ruler rather than a variable.
**Must never be added to the engineering score** — a blended number cannot tell you what changed.

## The feedback channel

`grid()` renders to a coarse text occupancy grid (default 64×32, ~450 tokens).

Why not an mmproj: with a vision projector, feedback fidelity becomes a *per-model* variable and
you end up measuring `drawing × seeing`. A fixed rasterizer gives every model **identical
information content**; only the ability to use it varies, which is the thing under test.

Why it counts as feedback at all: it carries information the model did not have. SVG→pixels
resolves geometry the model only approximated in its head. Re-reading its own SVG source would
*not* qualify — that is more thinking, not evidence.

## Validation (n=3, and that is the current weakness)

| reference | score |
|---|---|
| `reference/good.svg` — plausible duck on bicycle | 9/9 |
| `reference/blob.svg` — one grey circle | 5/9 |
| `reference/blank.svg` — near-empty | 1/9 |

**Known calibration weakness:** on `good.svg`, `clusters_similar_width` passed at 0.63 against a
0.60 threshold — marginal on a known-good input. The lower band also yields 4 clusters, not 2,
because frame strokes register and the check takes the two largest. Thresholds are calibrated on
one good example; they need several more before the score is trustworthy at the margin.

## Usage

```bash
python3 svg_probe.py drawing.svg --png out.png          # full JSON: checks, score, notes, grid
python3 svg_probe.py drawing.svg --grid-only --cols 64  # just the feedback channel
```

Requires `rsvg-convert`, PIL, numpy.
