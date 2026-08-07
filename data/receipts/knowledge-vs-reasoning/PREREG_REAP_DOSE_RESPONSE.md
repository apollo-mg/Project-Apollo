# Pre-registration — REAP dose-response: is expert-pruning damage linear, or is there a knee?

**Logged 2026-08-07, before any inference on any arm.** Models were selected by remote GGUF header
probe only (16.8 MB per file over HTTP range requests); no arm has seen a probe, and the probe set
is the unmodified campaign instrument.

## Why this leg exists

Every knowledge result in this campaign is **one ratio per model**. `CAMPAIGN_SYNTHESIS.md` lists
"one pair, one ratio, one pruner — no dose-response" as a standing limitation, and
`RESULT_QWEN_CALIBRATION_CONTRAST.md` could not attribute the GLM/Qwen difference because ratio,
calibration composition, and base model all varied together.

**This is the first leg where prune ratio is the only variable.**

## The instrument — G-1 passed before download

Five Q6_K arms, all `deepseek2`, verified by header probe before a byte was fetched:

| arm | packager | experts | pruned | tensor histogram | imatrix | size |
|---|---|---|---|---|---|---|
| **BASE** | mradermacher | **64** | 0 % | Q6_K 516 / F32 281 / Q8_0 47 | **none** | 24.61 GB |
| REAP-09 | Akicou | 58 | 9.4 % | *identical* | **none** | 22.48 GB |
| REAP-19 | Akicou | 52 | 18.8 % | *identical* | **none** | 20.34 GB |
| REAP-39 | Akicou | 39 | 39.1 % | *identical* | **none** | 15.70 GB |
| REAP-50 | Akicou | 32 | 50.0 % | *identical* | **none** | 13.21 GB |

Also identical across all five: `expert_used_count = 4`, `expert_shared_count = 1`,
`expert_feed_forward_length = 1536`, `expert_weights_scale = 1.7999999523162842`,
`expert_weights_norm = True`, `embedding_length = 2048`, `general.file_type = 18`.

**Imatrix is absent from all five arms**, which removes the asymmetry that voided the first Qwen
attempt (`RESULT_QWEN_CALIBRATION_CONTRAST.md`: 0xSero's pruned arm was imatrix-quantized and the
base was not). Here the packaging is uniform in the one respect that matters and the two packagers
produce byte-identical recipes.

**Recorded as a residual risk, not waved away:** the base comes from a *different packager* than the
four pruned arms. The recipe, histogram, imatrix status, and every architectural KV match, so what
remains is unobservable-from-the-header differences (llama.cpp version, source-weight revision). If
the base arm scores anomalously versus the campaign's existing GLM base, that is the first suspect.

## Design

`ikp_run.py` and `ikp_score.py` **unmodified**. 714 probes per arm (T1 200, T2 200, T3 165, T4 149)
after `--exclude-source researcher`. K=1, temp 0, `--no-think`, `-c 4096 -ngl 99 -sm layer -np 1
--jinja`, `.73` 2×P100 @ 1063 MHz / 150 W. Metric is **committed accuracy** —
`correct/(correct+wrong)`, excluding refusals and `NO_ANSWER` — as in every prior leg.

**Per-arm gates, asserted from the runtime's own `print_info` before probes are sent:**
`expert_count` must read 64 / 58 / 52 / 39 / 32 respectively, and `expert_gating_func` must match
across arms (G-1a — a GGUF omitting it is resolved by a hardcoded heuristic, so two arms can
silently run different gating).

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-L0** | **GATE** — base arm committed T1 ≥ 85 % | 0.80 |
| **P-L1** | T1 committed is non-increasing across 0→09→19→39→50 (3 pp slack between adjacent arms) | 0.80 |
| **P-L2** | **HINGE** — REAP-09 loses **< 10 pp** on T1 vs base: mild pruning is nearly free | 0.65 |
| **P-L3** | REAP-50 loses **> 40 pp** on T1 vs base | 0.70 |
| **P-L4** | The curve is **convex/accelerating** — T1 loss over 39→50 is ≥ 3× the loss over 0→09 | 0.60 |
| **P-L5** | Refusal rate rises **monotonically** with prune ratio | 0.55 |
| **P-L6** | Tail-selectivity is a **dose effect**: at REAP-09 T3+T4 loss ≥ 2× T1 loss; at REAP-50 T1 loss ≥ 25 pp (damage has gone broad) | 0.50 |

**P-L0 gates everything.** A base that cannot clear 85 % on T1 means the mradermacher packaging is
not comparable to the campaign's existing GLM base and the whole ladder needs re-anchoring.

**P-L2 is the hinge and the practically useful one.** "Can I prune 10 % for free?" is the question a
practitioner actually asks. 0.65 is honest: REAP removes lowest-saliency experts first, which argues
cheap early removals — but Cerebras at 25 % cost −36.8 pp, so if there is a knee it is already below
25 %, and 9 % may not be far enough beneath it.

**P-L1 is genuinely falsifiable, not a formality.** This campaign has twice seen a more-damaged
model score *better* on a metric: pruned GLM beat base on HumanEval+ (+1.22 pp), and the no-imatrix
Q3 beat its own BF16 parent on perplexity by 3.5 % (`Instrument_Disagreement_PPL_vs_KLD.md`). A
non-monotone rung here would be a third instance and would matter more than a clean slope.

**P-L6 is the reconciliation hypothesis and the reason it sits at 0.50.** GLM at 25 % was damaged
*uniformly* across tiers (falsifying P-X1); Qwen at 20 % was graded by obscurity. That has been
recorded as an open contradiction. If tail-selectivity is an early-dose phenomenon that saturates
into uniform damage as the ratio climbs, both observations are the same curve sampled at different
points. This ladder is the first instrument that can test it.

## Interpretation, fixed before the data

- **P-L2 holds and P-L1 holds** → there is a usable safe band, and the campaign can say where.
  That is the single most actionable thing it could produce for practitioners.
- **P-L2 fails** → damage begins immediately and there is no free lunch at any ratio. Combined with
  the falsified calibration mechanism, the practical claim becomes *expert pruning costs knowledge
  from the first expert removed*, which is a stronger and more publishable warning.
- **P-L4 fails with a concave curve** → early removals are the expensive ones, which would invert
  the saliency story REAP is built on and is the most surprising outcome available here.
- **P-L6 holds** → the GLM-vs-Qwen tier contradiction dissolves into a dose effect. That retires an
  open item rather than adding one.
- **P-L1 fails** → stop and check the arms before interpreting anything; a non-monotone ladder is
  either a real inversion or a packaging fault, and the two must be separated first.

## AMENDMENT 1 — 2026-08-07, after a VOID first run. Predictions unchanged.

**The first execution is void and is not scored.** G-5 tripped at a **93 pp** `no_answer` spread
(BASE 0.0 %, REAP-09 77.7 %, REAP-19 93.0 %, REAP-39 8.5 %, REAP-50 1.8 %), so every pruned arm's
committed accuracy was computed over a small biased remnant — two tier cells were literally `nan`.
No number from that run is reported anywhere.

**Cause — a gap in G-1 that this pre-registration did not cover.** G-1 verified the *weights*
(tensor histogram, expert counts, gating function, imatrix status: all identical). It never checked
the **tokenizer and chat template**. Read back from each arm's own load log:

| arm | `tokenizer.chat_template` KV |
|---|---|
| BASE (mradermacher) | **present** — kv 44, `[gMASK]<sop>\n{%- if tools -%}\n<\|syste…` |
| REAP-09/19/39/50 (Akicou) | **ABSENT** — no such KV (their KV indices are shifted by one) |

With no template in the GGUF, `--jinja` fell back to **ChatML**, which GLM-4.7-Flash was never
trained on. The pruned arms emitted `<|im_start|>` / `<|im_end|>` as literal text and looped to the
token cap, because the ChatML stop token is not an EOG in this vocabulary. Verified by spot test:
handed the correct template, REAP-09 answers `"The capital of Canada is **Ottawa**."` in 12 tokens
with `finish_reason=stop`. **The models were fine; the prompting was not.**

**Two instrument fixes, applied to all five arms identically:**

1. `--chat-template-file` with the authoritative template from `zai-org/GLM-4.7-Flash`
   (`chat_template.jinja`, 3120 bytes; its prefix matches the BASE GGUF's embedded template
   exactly). Passed to **every** arm including BASE, so parity is enforced rather than inherited.
2. `--max-tokens` **64 → 160**. Correctly-prompted GLM-4.7-Flash answers run 12–48 tokens here
   versus the base's 5–7, and a 64-token cap would reintroduce a differential-truncation gate trip.

**Why this is a broken-instrument repair and not a moved goalpost:** P-L0…P-L6 are all statements
about committed accuracy versus prune ratio. None mentions a token budget, none is made easier to
satisfy by a larger one, and the direction of every prediction is unchanged. The confidences are
**not** revised. What changed is that the arms are now prompted the same way — which the
pre-registration always assumed and failed to verify.

**Cross-leg comparison caveat:** earlier legs (`RESULT_QWEN_CALIBRATION_CONTRAST.md`,
`PHASE1_RESULT_COMMITTED_ERROR.md`) ran at `--max-tokens 64`. This leg's absolute numbers are
therefore not directly comparable to theirs; the ladder is internally consistent, which is what the
dose-response question needs.

**New standing gate for the campaign — G-1b.** Assert `tokenizer.chat_template` presence and
equality across arms before any inference, exactly as G-1a does for `expert_gating_func`. An absent
template is silently substituted, and a silent substitution changes both what the model is asked and
whether it can stop. Applies to `CAMPAIGN_SYNTHESIS.md`'s methodology table.

## Limits, known in advance

- **K=1, temp 0**, not reproducible on this fleet (`DETERMINISM_TEMP0_GLM_P100.md`). Existence
  proof, not rate. Five arms × 714 probes is enough to see a slope; it is not enough to put a
  confidence interval on any single rung.
- **One pruner (Akicou) across the four pruned arms.** The ratio is isolated; the *pruner* is not.
  Nothing here separates REAP-the-method from this person's application of it, and the ratios are
  their labels, not measurements — though the header probe confirms retained-expert counts of
  58/52/39/32 against a 64-expert base, which is consistent with the labels.
- **Imatrix-free throughout.** Today's ablation showed imatrix materially changes fidelity, so this
  curve describes static quants and may not transfer to imatrix-quantized deployments.
- **Cross-study comparison is indicative only.** The campaign's existing GLM numbers (93.5 % →
  56.7 %) come from unsloth **imatrix** packaging and a different pruner. Cerebras's 25 % point must
  **not** be plotted on this curve.
