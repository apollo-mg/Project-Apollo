# Result — whether a model can use visual feedback depends on the prompt's reference point

**Date:** 2026-09-10. **Model:** Qwen3.8-27B-GSQ-RCO **IQ3_XXS** (3-bit), llama.cpp on gfx1201,
`-ctk q8_0 -ctv q8_0 -c 40960`, temperature 1.0. **Instrument:** `tools/svgbench`.
**Artifacts:** `pass1.svg/png`, `pass2_full.json` (intent), `pass2b_full.json` (goal).

## Setup

Prompt: *"Generate an SVG of a pelican riding a bicycle."* The model cannot see its own output, so
feedback is a **coarse 64x30 text occupancy grid** rendered from its SVG — identical fidelity for
any model, unlike an mmproj, and it carries information the model did not have (SVG→pixels resolves
geometry it only approximated).

## Result

| pass | prompt framing | score | tokens | elapsed | outcome |
|---|---|---|---|---|---|
| 1 | initial draw | 10/11 | 3,937 | 135 s | excellent bicycle; pelican head **detached**, no neck |
| 2a | "compare the rendering **to what you intended**" | 10/11 | 9,386 | 336 s | **byte-identical output** |
| 2b | "**what is wrong** with this drawing" | **11/11** | 13,314 | 478 s | diagnosed and fixed the missing neck |

Single variable: the reference point of the review instruction. Same model, same starting SVG,
same grid, same temperature.

## The mechanism, from the reasoning traces

**2a did not fail to perceive.** It located everything correctly:
> *"The head is at cx=405, cy=112 — that would be around columns 30-40, rows 4-7. I see `-=`,
> `###`, `@@@@@` shapes there"*

then concluded:
> *"I'm satisfied the SVG is correct. Let me output it."*

It verified that each element was **where it had intended to put it** — and every element was.
It never asked whether the elements formed a coherent object.

**2b, given no reference to intent, found the exact fault:**
> *"**Missing neck:** The head circle (center 405,112 r 32) and the body ellipse (center 315,195
> ry 52) do not overlap; their closest edges are ~90 px apart horizontally, so the head appears to
> float in the air with no connection to the body."*

and made a minimal targeted repair — added a neck, changed nothing else.
Components 3 → 2, largest-component fraction 0.762 → 0.879.

**So the failure in 2a is not perception, it is reference point.** Self-review against one's own
plan is near-useless, because the plan is what produced the error. Review against the goal works.

## Why one-shot testing cannot find this

The famous pelican test scores pass 1 and stops. Dylan Castillo's study
(https://dylancastillo.co/posts/pelicanmaxxing.html) is far more rigorous — 48 animal×vehicle
combinations, 3 samples each, 1,008 SVGs, judged 1-5 — and finds no evidence labs special-case the
prompt. But it is still 1,008 **one-shots**. Neither measures whether a model can act on evidence
that it was wrong, which is the property that matters in agentic deployment.

## Caveats

- **n = 1 per arm**, temperature 1.0, not deterministic. The outcome difference needs reps; the
  reasoning traces are mechanistic evidence but not a rate.
- The intent-framed prompt was **written by me**, and it caused the failure it measured. That is
  the same class of error as the corpus's `t05_v4a` task asking for a format it never defined.
  Recorded rather than quietly dropped.
- The scorer was extended mid-run: pass 1 scored 9/9 on the original checks *with a floating head*,
  which is a ceiling effect. `assembly_coherent` (largest-component fraction ≥ 0.85) was added
  afterwards and is calibrated on n=4. Provisional.

## Side findings

- **This task needs a large budget.** At `max_tokens: 8000` it hit the cap mid-reasoning and
  returned **empty content**. At `-c 16384` it exhausted the context window. It needs ~9-13k
  generated tokens. The benchmark corpus specifies `max_tokens: 4096`, which would fail this task
  every time for reasons unrelated to drawing.
- **Framing changes reasoning length by ~40%**: 9,386 tokens (intent, plus "do not overthink this")
  against 13,314 (goal). Relevant to Qwen's own note that lower reasoning effort may not reduce
  total tokens in multi-turn work — the prompt appears to move it more than the effort dial might.
- A 3-bit 27B drew a structurally correct bicycle — spoked wheels, frame geometry, handlebars,
  chainring, legs reaching the pedals — blind, first attempt.
