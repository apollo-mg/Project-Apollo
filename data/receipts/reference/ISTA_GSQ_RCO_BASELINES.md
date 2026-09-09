# REFERENCE: ISTA's published GSQ-RCO baselines (quality vs bit-width, MTP acceptance)

**Source:** two charts published by ISTA on HuggingFace for `GSQ-RCO / QWEN3.8-27B`, seen 2026-09-09.
**Status: EXTERNAL, not measured by us.** Values below are read off published charts and are
approximate to ~0.1. Recorded because this is the **first external baseline we have for MTP draft
acceptance**, and it independently bounds what "normal" looks like.

---

## 1. Task average vs bit-width

Benchmark: mean of **AIME25, GPQA-Diamond, LiveCodeBench v6**. Base model = **91.87**.

| recipe | bpw | task avg | vs base |
|---|---|---|---|
| GSQ-RCO IQ3_S | ~3.50 | **91.7** | −0.2 |
| GSQ-RCO IQ3_XXS | 3.00 | **91.2** | −0.7 |
| GSQ-RCO IQ2_S | 2.75 | **89.6** | −2.3 |
| GSQ-RCO IQ2_XS | ~2.50 | **86.0** | −5.9 |
| Unsloth UD Q2_K_XL | ~2.87 | 89.7 | −2.2 |
| Unsloth UD IQ3_S | ~3.52 | 90.15 | −1.7 |
| **Unsloth UD IQ2_S** | **~2.49** | **78.3** | **−13.6** |

**Two things matter here.**

**A sharp knee at 3.0 bpw.** At and above 3 bits the loss is under a point. Below it, the curve falls
away fast: −2.3 at 2.75, −5.9 at 2.5. This is consistent with our own results — `GSQ-RCO-IQ3_XXS`
scored `valid_pass_rate 0.943` on the agent corpus, while an IQ2_M model could not complete a single
non-trivial task.

**At the same bit-width, recipe dominates.** GSQ-RCO IQ2_XS (2.50 bpw) holds **86.0**; Unsloth UD
IQ2_S (2.49 bpw) collapses to **78.3** — a **7.7-point gap at identical cost**. Nothing sub-3-bit is
uniform any more; these curves compare *where a recipe spends its bits*, not bit depth. Same lesson
as `gguf-label-is-not-a-spec`.

### Consequence for our 2-bit control panel

`GSQ-RCO-IQ2_XS-mtp` (8.17 GiB, on disk) is the **strongest available 2-bit contender** by the
vendor's own numbers, and it is the correct control for isolating bit depth — same base, same quant
family, same MTP head as the IQ3_XXS we already measured.

`UD-IQ2_M` remains useful for isolating the DavidAU merge (same nominal format, different packager),
but should be labelled a **known-weaker recipe**, not a neutral peer.

---

## 2. MTP draft acceptance — the number that matters for our bug

Benchmark: llama.cpp speed-bench, **3 draft tokens**, 5 samples per category, four quants
(IQ2_XS / IQ2_S / IQ3_XXS / IQ3_S).

**Published mean: 54.2%.** Range across all 11 categories × 4 quants: roughly **49% – 62%**.

| category band | acceptance |
|---|---|
| rag, multilingual, coding | ~58–62% (highest) |
| writing, summarization, qa | ~50–58% |
| roleplay, stem, reasoning, math, humanities | ~49–54% (lowest) |

Decode throughput in the same chart: **95–120 tok/s** (their hardware, not ours — our 9070 XT runs
43–60 t/s on this model, so only the *shape* transfers, not the level).

### This bounds our defect from outside

`viability/RESULT_TIMEOUT_WALL_ROOT_CAUSE.md` reports MTP acceptance collapsing to **0.000**
(0 accepted / 187 generated, `mean len` 1.00), reproduced twice on identical prompts, after the VBR
degrade order clamps at `--vbr-floor`.

**Zero does not appear anywhere in the vendor's characterisation.** Their floor across every category
and every quant is ~49%. A measured 0.000 is not the tail of a distribution — it is outside the
distribution. This is external corroboration that the collapse is a defect rather than variance, and
it is the single most useful sentence for the buun report.

### It also corrects an overcorrection of ours

On 2026-09-08 I hypothesised content-dependent acceptance, then **retracted it** when the collapse
proved time-correlated. This chart shows content-dependence is **real** — a ~13-point spread by task
category. Both are true:

- **normal** acceptance varies with content across ~49–62%
- **our** drop to 0.000 was a state defect, not content

The retraction was correct about the collapse; dismissing content-dependence entirely was an
overcorrection. Our own healthy pre-clamp measurements (0.44–1.00, mean 0.682) sit around and above
their band, which is consistent — our probe prompt ("count from 1 to 40") is far more predictable
than any of their categories, and scored 0.93–0.97.

---

## Limits on using this as a sanity check

**Their task average measures a different axis than our corpus does.** AIME25, GPQA-Diamond and
LiveCodeBench v6 are all **single-turn** reasoning and coding. None of them exercise multi-turn tool
use, state carried across turns, or stopping behaviour.

A model can score 86.0 on that average and still generate 8,300 tokens on *"read the tail of a
file"* — which is exactly what `RESULT_TURBO_IQ2M_WALLED.md` measured. **These curves tell us where
knowledge and reasoning degrade; they cannot tell us where agentic capability degrades.** Do not
quote the bit-width curve as evidence about agent viability.

Values are read from published charts, not from a table or a paper. Treat them as ±0.1 and do not
build a fine-grained argument on small differences.

## Who this is relevant to

- **buun** — the 49% floor bounds the acceptance-collapse defect from outside our own data.
- **Tom** (`llama-cpp-turboquant`) — recipe-vs-bit-width is directly his domain, and the 7.7-point
  gap between two ~2.5 bpw recipes is the kind of result that motivates the work he is doing on
  kernels and quantisation. He is also the natural person to sanity-check whether our reading of
  these curves is fair to Unsloth.
