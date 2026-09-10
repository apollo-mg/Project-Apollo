# Pre-registration — does quantization damage error correction differently from generation?

**Registered 2026-09-10, before any arm ran.**

## Question

Mark's framing: harnesses auto-correct, so if a lower bit depth reaches the same result but needs
extra passes, the user sees identical output and a longer wait. **Quantization may cost iterations
rather than quality** — which no pass-rate benchmark can see.

## Fit probe (measured before registering — `fit_probe.json`)

At the experiment's `-c 24576`, q8_0 KV, gfx1201:

| quant | size | VRAM | host spill (GTT Δ) | decode |
|---|---|---|---|---|
| UD-Q2_K_XL | 9.2 GB | 11.41 GB | 0 | 30.24 t/s |
| UD-IQ2_M | 9.6 GB | 11.89 GB | 0 | 28.05 t/s |
| UD-IQ4_XS | 13.3 GB | 15.29 GB | 0 | 31.38 t/s |
| UD-Q4_K_M | 15.3 GB | 15.90 GB (full) | **+1.08 GB** | **16.22 t/s** |

- **Q4_K_M spills into host memory** and decodes at about half IQ4_XS's rate despite being 15%
  larger. Its wall-clock times are confounded and are **excluded from every time comparison**.
- **IQ4_XS decodes faster than Q2_K_XL** while 45% larger: on gfx1201 decode speed is not
  proportional to file size (IQ and K dequant kernels differ). Wall time is a poor cost proxy across
  quant types even without spill.
- **Therefore completion tokens are the primary cost metric** — independent of where weights live.

## Correction carried in

`../svgbench-run/RESULT_REFERENCE_POINT.md` compared prompts that differed in **three** ways
(review clause, a fault-list output format, and "do not overthink this"), not one. Its
reference-point conclusion is confounded. This design varies **only** the review clause.

## Design

- **Model:** stock Qwen3.8-27B, unsloth UD ladder — Q2_K_XL, IQ2_M, IQ4_XS, Q4_K_M.
- **Server:** buun-llama-cpp `3823c9eb6`, `-c 24576 -ctk q8_0 -ctv q8_0` (**no VBR** — the
  degeneracy fault lives there), `--reasoning-effort medium` (injects no text), temperature 1.0,
  `max_tokens` 20000.
- **3 reps per quant, interleaved rep-major**; fresh server per (quant, rep).
- **Per rep:** `p1` initial draw → from the *same* p1, `intent2` and `goal2` (paired) → if `goal2`
  is below max, `goal3` from `goal2`.
- **Feedback:** 64×30 occupancy grid of the parent's render (`tools/svgbench/svg_probe.py`).
- **The only difference between arms** — scaffold, output format and every other word shared;
  confirmed by a character-level diff in the runner's `--dry-run`:
  - intent: *"Compare the rendering to what you intended."*
  - goal: *"Judge the rendering as a picture of a pelican riding a bicycle."*
  - both then: *"List its faults briefly (or write "none"), then output a complete corrected SVG."*
- **Scorer:** `svg_probe` structural, 11 checks, per-check results recorded for flip analysis.
  `assembly_coherent` threshold (0.85) is **provisional**, calibrated on n=4.
- **Persistence:** one JSONL line per generation with flush+fsync; resumable.
- **GPU junction / sclk / power snapshot per generation** (`gpu-clock-benchmark-discipline`).

## Pre-specified metrics

- `p1_score`
- `gain(f) = score(f2) − score(p1)`, paired within rep
- `framing_effect = gain(goal) − gain(intent)`
- `converged_at` — first pass in the goal chain at max (1, 2, 3, or none)
- `tokens_to_converge` — cumulative completion tokens through `converged_at`
- `identical_to_parent` rate per framing
- **regressions** — any correction pass scoring below its parent
- **Ceiling rule:** if `p1` is already max, gain is undefined and that rep is excluded from
  `framing_effect` means; it is still reported, and any drop counts as a regression.

## Predictions

| | claim | conf |
|---|---|---|
| **P-L1** | `framing_effect > 0` on average over non-ceiling reps | **60%** — lowered from the 75% I'd have logged this morning, because that evidence confounded three variables |
| **P-L2** | mean `p1_score` of the two Q2-class quants < mean of the two Q4-class quants | 60% |
| **P-L3** | median `tokens_to_converge` higher for Q2-class than Q4-class | 55% |
| **P-L4** | the relative drop in mean goal gain from Q4-class to Q2-class **exceeds** the relative drop in `p1_score` — error correction degrades faster than generation | **50%** |
| **P-L5** | `identical_to_parent` rate higher for intent than goal | 65% |

## What will not be claimed

Three reps per quant, one prompt, one model family, one structural scorer with a provisional
threshold. This is a pilot that sizes effects; it does not establish rates. The scorer measures
assembly and structure, not whether it is a good pelican — that judgement stays with the viewer.

---

## PROTOCOL CHANGE (2026-09-10, 19:05–19:30) — instrument revised after the first rep; first run quarantined

Made **before any valid outcome was observed.** The first run's data is garbage (below) and informed
only the diagnosis.

**1. Backdrop detection** (`svg_probe._ink`): corner-median → per-pixel comparison against the
colours at the ends of its own row and column, after compositing onto white.
*Cause:* rep 1's drawing had sky over ground; the corner median, rgb(186,208,203), matched neither;
**99.7% of the canvas registered as ink** and every correction step was fed a solid block of `@`.
Both fault lists said so. All four steps invalid → `invalid_bg_run/` with `CONTAMINATED.md`.

**2. `assembly_coherent` redefined:** `largest_component_frac >= 0.85` → *no component of at least
5% of the main subject's size lies within 6 cells (~24 px) of it.*
*Cause:* once (1) was fixed, pass1's wheel shadows joined its ground line to the bicycle, the
fraction rose 0.762 → 0.889, and the **detached head passed** — the exact fault the check exists
to catch. A threshold on "fraction in the biggest piece" moves whenever unrelated scenery merges.

**3. `clusters_similar_width` removed from scoring** (kept as note `cluster_width_ratio`).
*Cause:* column-projection runs merge frame and crank into the rear-wheel run. It was already marginal
on a known-good reference **before any data** (0.63 vs 0.60, recorded in the README at creation), then
failed a correct real drawing. It penalises added detail — a bias that would fall on the higher-bit
quants. **Scored max is now 10.**

### Validation after the change — every case matched expectations written before the run

| case | expected | got | note |
|---|---|---|---|
| good (plain backdrop) | 10/10 | 10/10 | 1 component, 1440 cells |
| good_transparent | 10/10 | 10/10 | backdrop invariance |
| good_vgradient | 10/10 | 10/10 | backdrop invariance |
| good_hgradient | 10/10 | 10/10 | backdrop invariance |
| good_skyground | 10/10 | 10/10 | the failure mode; wheels straddle the horizon |
| blob | 7/10 | 7/10 | |
| blank | 1/10 | 1/10 | |
| pass1 (detached head) | 9/10, assembly FAIL | 9/10 | near fragment 213 cells = the head |
| pass2b (neck fixed) | 10/10 | 10/10 | one component |
| real_q2_skyground | 10/10 | 10/10 | sun + cloud (188, 102 cells) correctly ignored as distant |

Backdrop invariance: the same subject on five backdrops yields component sizes 1432–1444 and grids
differing by 1–10 of 2048 cells.

### Disclosed researcher degree of freedom

Changes 2 and 3 were made **after seeing specific drawings** (pass1, real_q2). Mitigation: each is
motivated by a mechanism (threshold drift from unrelated merges; projection merging), not tuned to a
target number, and pass criteria were written before re-validating. It is still a choice made with
data in view and is disclosed as one.

**Predictions P-L1–P-L5 and all metric definitions are unchanged.** The ladder restarts from scratch.
