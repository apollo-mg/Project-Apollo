# At a fixed KV budget, bits belong on V — clean test, two independent codec families

**2026-08-18**, `.194`, quad Tesla P100 (sm_60), 150 W. buun `02f8581`,
`Qwen3.8-27B-Q6_K` (arch `qwen35`, `n_layer 64`), D=256, GQA 6:1.
`llama-frontier-hazard`, 128 wikitext prompts, `--n-prefix 128 --n-score 128`,
teacher-forced vs f16/f16. Raw `u5f.log`, script `u5f_clean.sh`.

Pre-registered in `RESULT_U5CD_PLACEMENT.md` (`0a77b10`) **before the run**, at confidence
**0.55** that the V direction would replicate, with the falsifier stated: *"if it reverses or
ties, the U5d result was a turbo-codec property being read as an allocation law."*

**Read with `SCOPE_CORRECTION_136_TOKENS.md`. Everything here is a 136-token measurement.**

## Why this test exists

`U5d` found the richer codec worth more on V than on K, but compared **turbo2 against
turbo3** — two codecs differing in design, rotation-group handling *and* kernel dispatch. It
licensed only a claim about those codecs. Mark's standing warning is exactly this failure:

> *"Every time I try and measure KV effects, we always hit a point where my agent says 'V
> effects appear to contradict the status quo, giving preference to K'… then we realize our
> measurements aren't measuring the right thing. Pretty much every time."*

`q8_0` and `q4_0` remove every confound at once: same codec family (plain block-scalar quant
with a per-block `ggml_half` scale), differing **only in bits**. No FWHT. No turbo kernel.
`turbo_k_any` is false for both, so the `fattn.cu:2638` Q-pre-rotation branch that wrecked
U5d's symmetry arms **cannot fire**. And `RESULT_U5E_KVSIZE.md` established that stock types
allocate **exactly** their block layout at every context size, so the two mixed arms are
genuinely equal-cost rather than nominally so.

## Result

| arm | K | V | total bpv | flip_rate | mean_KL | mean_R | cvar95_R |
|---|---|---|---:|---:|---:|---:|---:|
| A | `q8_0` | `q8_0` | 17.0 | 0.0014 | 0.00001 | 0.1654 | 3.3529 |
| B | `q8_0` | `q4_0` | 13.0 | 0.0176 | 0.00123 | 19.1165 | 380.81 |
| **C** | **`q4_0`** | **`q8_0`** | **13.0** | **0.0149** | **0.00098** | **11.9020** | **238.52** |

**Spending the spare bits on V is 37.7 % better on the mean and 37.4 % better on the tail, at
identical cost.** `flip_rate` (0.0149 vs 0.0176) and `mean_KL` (0.00098 vs 0.00123) agree.
All four metrics, same direction.

## Two independent families, same answer

| test | codecs | K-rich | V-rich | V better (mean) | (tail) |
|---|---|---:|---:|---:|---:|
| U5d | turbo3 / turbo2 | 401.83 | 274.60 | **31.7 %** | 31.4 % |
| U5f | `q8_0` / `q4_0` | 19.12 | 11.90 | **37.7 %** | 37.4 % |

Different codec families, different bit tiers, 20× different absolute error — **same
direction, comparable magnitude.** The allocation finding has now survived removal of the
codec-quality confound, the kernel-dispatch confound, the allocation-arithmetic confound, and
the small-sample confound.

**`P5a` confirmed. The V direction is real at this depth.**

## What it does and does not contradict

It runs against the stated community intuition. h4rm0n1c:

> *"You can lose a value and a key might point to something near enough, but if you lose the
> key, no value at all gets found."*

**That is not refuted by this, because it is a claim about a different regime.** His intuition
comes from long-context use; every number here is from a 136-token cache. buun's refinement
points the same way — *"K > V is a generalization but not true on a layer-by-layer basis."*

### Hypothesis for the discrepancy, with a falsifiable prediction

K errors perturb attention **scores**, which pass through a softmax; V errors perturb the
**output** directly, as a weighted average of V vectors.

- At **short context**, attention concentrates on few positions, so V error passes through
  nearly undiluted while a peaked softmax absorbs score noise.
- At **long context**, attention spreads over many positions, so V errors **average out**
  (variance falls roughly as 1/n of the effective attended set), while K errors get *worse* —
  retrieval must discriminate among a larger candidate pool, so a score perturbation is more
  likely to change which token wins.

**Prediction: the V advantage shrinks with depth and inverts at some crossover.** That is
directly testable by re-running exactly these four arms at increasing `--n-prefix`, and it
would reconcile our measurement with h4rm0n1c's experience rather than pitting them against
each other. **Untested — the instrument has never been run above 136 tokens
(`SCOPE_CORRECTION_136_TOKENS.md`).**

If the crossover exists, it also bears on buun's layer-pricing tables, which price K and V
separately (`scripts/make-vbr-pricing-tables.py`, `side` column): a schedule swept at one
depth would be mispriced at another. **At what depth the sweep was run is an open question
for him** — it is not stated in `docs/vbr.md`, and the methodology file
(`knowledge/measurement-methods.md` §2/§8) lives in `buun-quality-bench`, which we do not have.

## The ~20× tail/mean ratio holds again

| arm | cvar95_R / mean_R |
|---|---:|
| `q8_0`/`q4_0` | 19.92 |
| `q4_0`/`q8_0` | 20.04 |

Across every scored arm in U5c/U5d/U5f — **19.91 to 20.27**, over a >3,000× span in mean_R.
The error distribution's *shape* is invariant to codec and to allocation; only its scale
moves. At this depth the tail carries no ranking information the mean does not.
