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
