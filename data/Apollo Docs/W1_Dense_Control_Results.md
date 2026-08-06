# W1 Dense Control — Is Puzzle's Q4 brittleness NAS-specific or generic?

**Date:** 2026-07-13 (Architect-driven, overnight). **Rig:** 4× Tesla P100 (sm_60), node `.194`.
**Build:** `~/llama_stock/build_carveout` — stock `9967 (4f37f5197)`, sm_60 FAST_FP16 carve-out
applied (fp32-clean arithmetic). **Corpus:** wikitext-2 test, md5 `7c0137fc034ddbc56a296bce31b4f7fb`,
2048 ctx / 32 chunks. **Protocol:** f32 KV, FA off, `-ub 128`, `-ngl 99 -ts 1,1,1,1`.
**Receipts:** `.194:~/puzzle_lab/w1/{truthbase_qwen_q8.log,kld_qwen_q4km.log}`.

## Setup discipline (after the 2026-07-13 fabrication incident)

Both models freshly downloaded from **unsloth/Qwen3.6-27B-GGUF** and byte-verified against the
HF API by the Architect (not trusted from Gemini): Q8_0 = 28,595,763,424 B, Q4_K_M =
16,817,244,384 B. The Q4_K_M is **imatrix-calibrated** (`quantize.imatrix.file =
imatrix_unsloth.gguf`), matching Puzzle's imatrix Q4_K_M — so the *only* variable between the
two panels is model architecture, not quant recipe. Prior lmstudio-community (static, non-imatrix)
files quarantined to `27B/lmstudio_static/` as a secondary data point. Qwen Q8 base PPL 6.5333
(consistent with buun's independent 3090 Qwen base 6.5526 — sanity check passed).

## Result — the control lands on top of the NAS model

Both are imatrix Q4_K_M scored against their own Q8_0 truth base, identical protocol:

| metric (vs own Q8 truth) | Puzzle-75B-A9B (NAS-pruned hybrid MoE) | Qwen3.6-27B (non-NAS control) |
|---|---|---|
| **Same-top %** | **94.010 ± 0.131** | **94.862 ± 0.122** |
| Median KLD | 0.007221 | 0.004878 |
| Mean KLD | 0.018732 | 0.050234 |
| 99.9% KLD | 0.421621 | 10.751770 |
| Max KLD | 1.405820 | 28.715385 |

Puzzle receipts: `~/puzzle_lab/kld_q4km.log`. Qwen receipts: `~/puzzle_lab/w1/kld_qwen_q4km.log`.

## Prediction P-W1: FALSIFIED (Architect reversal #11)

Logged prediction: "*Qwen3.6-27B Q4_K_M scores same-top ≥ 97.5% … i.e., the dense control shows
Puzzle's 94.0% to be NAS-anomalous.*" **Actual: 94.862%.** The control did **not** clear 97.5% —
it landed within 0.85 pp of the NAS model. The stated dissolution condition ("if Qwen lands ≤ 95%,
the brittleness claim dissolves") is met.

## What it actually means

1. **The NAS-brittleness hypothesis is dead** (in its strong form — that NAS pruning *explains*
   Puzzle's 6% loss). Q4_K_M (imatrix) disagrees with its **Q8_0 reference** on ~5–6% of greedy
   tokens on **both** a NAS-pruned 75B hybrid MoE and a standard 27B — ~1 in 17 (Puzzle), ~1 in 19
   (Qwen). A *small* NAS penalty is statistically real (Puzzle 94.010 ± 0.131 vs Qwen 94.862 ±
   0.122 — non-overlapping, ~0.85 pp / ~17% more flips proportionally), but it is a second-order
   effect riding on a large shared baseline, not the catastrophe the hypothesis predicted. Note the
   reference is **Q8_0 weights**, not full precision; Q8_0 is a near-lossless proxy (standard
   practice), and both sides ran fp32-clean arithmetic (f32 KV, patched sm_60) so the measured
   delta is the *weight* difference Q4→Q8, uncontaminated by Pascal's fp16 arithmetic fog.

2. **The bigger, real finding replaces it:** *Q4_K_M is less lossless than "Q4_K_M is basically
   free" folklore implies.* ~5% greedy-token disagreement with Q8_0 is much larger than the small
   perplexity delta between Q4 and Q8 suggests — this is a **metric** point (per-token same-top vs
   corpus-mean PPL), which the community's PPL-delta habit hides. Measuring with fp32-clean
   arithmetic matters only to keep the weight effect clean of Pascal's arithmetic error; the
   flip-rate itself is a weight-quant fact visible against any Q8 reference. Affects everyone
   shipping Q4_K_M, not just NAS users — and is a natural companion piece to the sm_60 arithmetic
   finding (that one: arithmetic precision; this one: weight precision).

3. **Architectural tail signature (OBSERVATION, receipted):** the dense control has a *better
   median* (0.0049 < 0.0072) but *far heavier tails* — max KLD 28.7 vs 1.41, 99.9% KLD 10.75 vs
   0.42, 99.9% Δp 51% vs Puzzle's much gentler tail. The NAS-pruned MoE's worst-case divergence is
   ~20× tighter. Its typical token is slightly worse; its catastrophic flips are dramatically rarer
   and smaller.

4. **SPECULATION (marked, unproven):** MoE routing may localize quantization error — a poorly
   quantized expert only damages tokens routed to it (bounded), whereas a dense layer's bad
   quantization can propagate globally on certain tokens (rare catastrophic flips). A per-token /
   per-expert decomposition (jlens-gguf territory) could test this. Do not publish as fact.

## Caveats for any public write-up

- The two Q8 truth bases were generated on different offload configs (Puzzle: build_puzzle,
  -ngl 40 partial CPU offload; Qwen: build_carveout, -ngl 99 full GPU) — both fp32-clean arithmetic,
  so comparable, but note it.
- "Non-NAS control" not "dense" — Qwen3.6-27B's exact architecture (dense vs hybrid) is unconfirmed
  here; the controlled variable is NAS-pruning presence/absence, not attention density.
- Secondary panel available if wanted: the quarantined lmstudio **static** (non-imatrix) Q4_K_M vs
  the same Q8 base would isolate the imatrix contribution — RUN, see addendum below.

---

# Addendum — Publisher Panel: does *which* Q4_K_M you download matter?

**Question:** "Q4_K_M" is treated as one thing. Is it? Compared unsloth's Q4_K_M (W1) against
lmstudio-community's Q4_K_M of the same model, both scored against the **same** unsloth-Q8 base
(identical reference frame), same protocol (f32 KV, FA off, 32 ch, build_carveout).

**The two "Q4_K_M" are not the same recipe** (tensor-type inventory, both 851 tensors):

| | unsloth (16.82 GB) | lmstudio (16.55 GB) |
|---|---|---|
| Q4_K | 289 | 433 |
| Q5_K | 48 | 0 |
| Q6_K | 65 | 65 |
| F32 | 449 | 353 |
| imatrix | yes (`imatrix_unsloth.gguf`) | no (static) |

unsloth ships a *dynamic* recipe (more tensors upcast to Q5_K/F32) **and** imatrix; lmstudio ships
the uniform textbook Q4_K_M, static. Two variables move together.

**Result (both vs the identical unsloth-Q8 base):**

| metric | unsloth dynamic+imatrix | lmstudio uniform+static | Δ |
|---|---|---|---|
| **Same-top %** | 94.862 | **92.693** | **−2.17 pp** |
| Median KLD | 0.004878 | 0.009763 | **2.0×** |
| Mean KLD | 0.050234 | 0.093935 | 1.9× |
| 99.9% KLD | 10.75 | 16.96 | worse |
| Max KLD | 28.72 | 28.29 | ~tie |

Receipt: `~/puzzle_lab/w1/kld_lmstudio_static_q4km.log`.

**Prediction P-pub: WRONG (Architect reversal #12).** Logged: same-top gap 0.5–1.5 pp. Actual:
**2.17 pp** — the ">2 pp = publisher choice matters a lot" branch fired.

**What it means:**
- Two files both named `Qwen3.6-27B-Q4_K_M`, same model, differ by **2.17 pp same-top** — from
  ~1-in-19 greedy flips vs Q8 (unsloth) to ~1-in-14 (lmstudio), **~42% more token divergence** for
  the same nominal quant. Median KLD **doubles**.
- The effect is **across the whole distribution, not just tails** — median doubling means the bulk
  moved, refuting the "imatrix only rescues rare tokens" intuition for this recipe pair.
- This sharpens the W1 finding: W1's ~5% loss was the *good* (dynamic) Q4_K_M; a vanilla static one
  loses ~7%. "Q4_K_M" is a quality range, not a point, and it's publisher-dependent.
- **Attribution caveat (honest):** imatrix and tensor-allocation differ simultaneously — this
  measures the *combined* publisher-recipe effect, not imatrix alone. A same-allocation
  imatrix-vs-not pair would isolate it; not available here.
- **Minor bias note:** both Q4s scored against unsloth's *own* Q8, which could very slightly favor
  unsloth-Q4 (correlated pipeline). A true dequantized-fp32 base would remove it; the 2.17 pp gap
  is large enough to survive that small potential bias.
