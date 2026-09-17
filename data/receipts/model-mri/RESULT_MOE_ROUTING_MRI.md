# Result — Model MRI resurrected: MoE expert-routing, locality, and fine-tune diffs

**2026-09-16.** Exploratory (hypothesis-generating), not a preregistered confirmatory study — the numbers
below are a first look, and the informal predictions made in-flight are scored honestly at the end.
Tooling: `tools/model-mri/` (capture + analysis). Motivated by the edge0 paper
(`prediction-is-routing` SSD-MoE streaming) and the "everything is MoE now" reality.

## Setup

- **Capture**: `llama-moe-capture` (buun-llama-cpp `cb_eval` hook) dumps per-layer per-token `ffn_moe_probs`.
- **Models**, same **UD-Q5_K_XL** quant so the only variable is the fine-tune, not the quantizer:
  - coder: `Cyber-Tiel-Coder-35B-A3B-MTP-UD-Q5_K_XL`
  - base:  `Qwen3.6-35B-A3B-UD-Q5_K_XL` (unsloth) — Cyber-Tiel's base family
- **Corpora** (`corpora/`): one code sample (435 tokens) + one prose sample (269 tokens). CPU capture,
  temp-0 prefill (deterministic), K=8, 40 MoE layers × 256 experts. Same tokenizer verified (token counts match).

## Finding 1 — routing behaviour (Cyber-Tiel)

Adjacent-token top-8 **overlap** (routing locality): **code 0.33, prose 0.45** — both *above* edge0's ~0.25
general baseline, so this model's routing is more step-to-step predictable than their number.
- **Prose is more local than code** (0.45 vs 0.33). Plausible: a single-topic narrative keeps hitting the
  same experts; code churns experts token-to-token across keywords/identifiers/operators/punctuation.
- **Locality is depth-structured**: ~0 at layer 0 (input routes near-randomly token-to-token), peaks in the
  **mid-stack** (L15–30, up to 0.45 code / 0.60 prose), tapers late. The single "25%" average hides this.
- Router is **soft**: entropy ~7.5 of 8.0 bits (near-uniform), top-8 mass only 13–18%; **0 dead experts**.

Figure: `mri_heatmap.png` (layer×expert utilization, code | prose, + locality-by-layer).

## Finding 2 — how the coder fine-tune reshaped routing (base vs Cyber-Tiel)

Token-aligned top-8 **preservation** (1.0 = identical routing to base, 0 = fully rewired):
- **Largely preserved**: **code 0.75, prose 0.86** mean. The fine-tune kept the base's routing backbone.
- **Changes concentrate in the last ~4 layers**: early layers barely move (L0–5 at 0.88–0.92), then code
  preservation collapses to **0.43 at L38** (utilization TV spikes ~3.0 there). Textbook "generic early,
  task-specific late," measured directly on routing.
- **Domain-targeted**: code is rewired far more than prose everywhere, dramatically so late (0.43 vs 0.79 at
  L38). A *coder* fine-tune reshaped how code routes and left prose mostly alone.

Interpretation: specialization is **late and targeted at the trained domain**; the coder's value lives in
the *contents* of its late-layer experts. Figure: `mri_diff.png`.

## Prediction scorecard (informal, made before each result)

| prediction | outcome |
|---|---|
| code routes *more* locally than prose (structured/repetitive) | **WRONG** — prose is more local (0.45 vs 0.33) |
| fine-tune *largely preserves* base routing, changes in *late* layers | **RIGHT** — 0.75/0.86 preserved, rewiring at L36–39 |

## Caveats

- **N=1 corpus each** — the exact numbers are a first look; the late-layer concentration and code>prose
  asymmetry are strong/consistent, but multi-sample runs are needed before any number is a rigorous claim.
- CPU capture; K fixed at 8; **softmax-top-k family only** — DeepSeek/GLM sigmoid-group routing needs the
  masked-variant capture (see `tools/model-mri/README.md`).

## Next

Multi-sample corpora for a real locality/preservation number; sigmoid-group support (to MRI DeepSeek-V4.1);
expert-specialization analysis (what do the hot late-layer coder experts actually fire on).
