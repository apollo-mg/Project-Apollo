# Flash-Next pelicans — INFORMAL, deliberately NOT part of the svgbench blind panel

**2026-09-14 09:48–09:56, `.194`**, Flash-Next **UD-IQ4_XS** at `-ncmoe 2 --numa distribute` (the machine's
best config, 61,712 MiB), buun `c7f114d34`. Prompt and temperature match the panel — *"Generate an SVG of a
pelican riding a bicycle."*, temperature 1.0 — **but this is 3 reps with thinking off, where the panel runs
5 reps per arm with each arm's shipped template.** It is not an arm and must not be scored beside one.
Folding Flash-Next into the panel needs a dated amendment and a fresh blind round with the outside raters.

| rep | tokens | tok/s | SVG chars | read |
|---|---|---|---|---|
| 1 | 2,575 | 18.6 | 5,197 | **best bicycle** — diamond frame, chainring, crank, grips. Bird reads goose-ish |
| 2 | 2,956 | 18.7 | 5,654 | **best pelican** — correct pouched beak, S-curve neck, wing reaching the handlebar. Simpler frame, bird oversized |
| 3 | 3,188 | 18.7 | 6,498 | most bicycle detail (seat post, stem, pedals) but **weakest composition** — bird swallows the frame, beak lost its pouch |

**All three produced valid SVG; thinking fired on none (0 reasoning chars), as configured.**

**Two observations, both n=3 and not claims:**
- **No rep did both well.** Bicycle quality and pelican quality traded off across reps. A single draw would
  have mischaracterised the model in either direction — which is the argument for the panel's 5-rep design.
- **More tokens did not mean a better drawing.** The longest rep (3,188) is the weakest composition and the
  shortest (2,575) the strongest.

**Decode here is 18.6–18.7 tok/s, against the ladder's 22.33** — these are 2.5–3.2k-token generations with
growing context, not the ladder's 128-token fixed-prompt measurements. **Not a regression; a different
measurement shape.**

Renders were produced with `rsvg-convert` at each file's own viewBox aspect. **A first render of rep 1 forced
500×400 into 700×700 and silently distorted it** (its `<circle>` sun became an ellipse); the files here are
the corrected ones.
