# Lab Spec — Does compression eat knowledge faster than reasoning?

**Status:** proposed, 2026-08-06. Inherits `Protocol_Measurement_Standard.md` in full; this spec
states only what is specific to the question.
**One-line claim under test:** *knowledge recall degrades under compression far faster than reasoning
does, and the benchmark panels the field actually uses are structurally blind to it.*

## Motivation — four independent signals, one unmeasured axis

| source | observation |
|---|---|
| Maple-Preview (20B-A1B ternary) | vendor panel is LCBv6 / AIME 2026 / HMMT 2026 / GPQA-D — all reasoning. Independent testers found confident factual fabrication within hours |
| Qwen3.6-35B-A3B vs Qwen3.5-122B-A10B | newer/smaller wins AA index (32 v 28) and SWE-bench (73.4 % v 72 %), **loses MMLU-Pro (64.7 % v 67.1 %)** — it loses only on the knowledge benchmark |
| REAP paper (arXiv 2510.13999, Cerebras) | headline is *"near-lossless on **code generation**"*; authors themselves distinguish generative from discriminative. Shipped models are `Qwen3-Coder-REAP-*` |
| r/LocalLLaMA field report | *"works fine in a Q6 or Q8 quantized LLM but breaks down in a bad way at worse quantization"* — specifically for esoteric factual recall |

Nobody has measured the two axes **on the same arms with a tiered instrument**. That is the gap.

## Two compression mechanisms — do not conflate

- **M-A — precision reduction (quantization).** Every weight keeps its place, loses fidelity.
- **M-B — capacity deletion (REAP expert pruning).** Whole experts are removed.

**M-B carries the sharper prediction.** REAP ranks experts by router gate-value × activation norm
over a calibration set and deletes the low-scoring ones. Experts that fire rarely on that calibration
distribution are cut — and rare firing means rare inputs, which means tail knowledge. REAP's
selection criterion is close to a *direct proxy* for "delete the tail of the knowledge
distribution," and its published calibration is general/code/reasoning, which will not light up an
expert that only fires on obscure facts.

If the thesis is right anywhere, it is right here, and for a stateable reason.

## Instruments

**Knowledge — IKP** (`data/receipts/ikp/`: `ikp_run.py`, `ikp_score.py`, `ikp_probes.json`).
1,400 short-answer questions, 200 per tier × 7 tiers, answers averaging ~1.5 words, tiered by
obscurity. **T1–T4 only, 800 questions.** T5–T7 are excluded: the upstream audit
(`BenSturgeon/ikp-replication`) flags them 100 % researcher+wikidata sourced and they sit at the
noise floor (10 % / 3 % / 4 %).

Exact-match scoring means **no reference logits are required**, which is what makes this runnable on
the 16 GB control plane rather than `.194`.

**Reasoning — HumanEval+**, existing harness and receipts (`data/receipts/humaneval-plus/`).

Both instruments run on **every** arm. The deliverable is both curves on one pair of axes.

## Contamination — why the paired design neutralises it

IKP is a public question set, so contamination is possible. This is the one property KLD has that
IKP does not (§3: KLD is contamination-immune by construction).

**It cancels.** Every comparison here is a *delta between arms derived from the same base model*.
Whatever the base memorised from contamination, the compressed arm inherited the same exposure. A
contaminated question inflates both arms equally and drops out of the difference. Absolute IKP
scores are therefore **not** reportable as capability claims; only deltas between arms are.

State this in the write-up unprompted — it is the first objection a reader will raise.

## Phase 0 — gates, non-negotiable

**G-1 — packaging parity (§2).** We cannot run REAP ourselves, so both Phase 1 arms are third-party
artifacts. The minimum control is that **both GGUFs come from the same packager with the same
recipe**. `unsloth` ships both the base and the REAP variant, which satisfies this *only if* the
quant recipe matches. Unsloth Dynamic (UD) quants use an imatrix; **if the imatrix corpus or the
per-tensor recipe differs between the two models, the comparison measures packaging, not pruning.**
Verify by dumping both files' `quantize.imatrix.*` KVs and per-tensor type maps. If they differ, fall
back to plain (non-UD) quants of the same type, or quantize both ourselves from safetensors.

**G-2 — instrument discrimination.** Run IKP T1–T4 on the **base** arm first. If the base scores near
ceiling or near floor on a tier, that tier cannot measure damage and must be reported as
uninformative rather than silently included. Record per-tier base accuracy before any compressed arm
runs.

**G-3 — positive verification (§1).** For every run, `grep -c` the scored-question count in the
output and require it to equal the expected 800. A run that scores 0 questions exits 0 and reports
100 % of nothing. Guards abort, do not warn.

**G-4 — prune ratio.** Confirm the actual expert count per layer in both Phase 1 arms from the GGUF
metadata rather than from the model card's claimed ratio (§5 — measure the property, don't read the
label).

**G-5 — separate "wrong" from "never answered." This campaign's most likely false positive.**

GLM-4.7-Flash is a reasoning model. If an arm's `<think>` chain fails to terminate inside the token
budget there is no answer to extract, and a naive scorer books it as **wrong**. That reads as
knowledge loss and is not — it is a stopping-rule failure. A pruned reasoning model is, if anything,
*more* likely to produce one.

**This has already happened in this lab.** The Puzzle-75B HumanEval+ gap
(`data/receipts/humaneval-plus/`) was a stopping-rule failure, not an answering failure. Same shape,
different campaign.

Required, therefore:

- Set `n_predict` / token cap **in advance** and record it (§9). Never leave it at a default.
- Score every response into **three** buckets, never two: `correct`, `incorrect`, `no_answer`
  (truncated, looped, or unparseable).
- Report `no_answer` **per arm and per tier**, alongside the accuracy figures and never folded into
  them.
- **If `no_answer` rates differ between arms by more than 2 pp, the knowledge delta is not
  interpretable** until that difference is explained. Divergent termination behaviour is its own
  finding and possibly a more interesting one — report it as such rather than as a knowledge result.
- Accuracy is reported over *answered* items with `n_answered / n_total` stated, so a reader can see
  the denominator.

Running IKP with thinking disabled (see Modes below) is the primary mitigation, not a substitute for
the accounting.

## Modes (§6)

Each instrument runs in the mode appropriate to it; both arms always identical, both recorded.

| instrument | mode | rationale |
|---|---|---|
| IKP T1–T4 | **thinking OFF** | recall is not a reasoning task. A `<think>` chain adds nothing to a 1.5-word factual answer while multiplying token cost and loop risk |
| HumanEval+ | **thinking ON** | the mode the model is designed and tuned for |

Enumerate the available modes from the model's own chat template rather than assuming a `/nothink`
toggle exists; if it does not, say so and run both arms with thinking on, with G-5 doing the work.

## Sampling

Unsloth's recommended parameters for this model are **temp 1.0 / top_p 0.95 / min_p 0.01 / no repeat
penalty**. We deviate deliberately: **temp 0 on both arms** for the primary measurement, because this
is a paired delta, both arms are equally off-recipe, and a ~5 pp effect cannot survive temp-1.0
variance at any K we can afford.

Record the deviation per §9. If the effect appears, confirm it on a subset at the recommended
parameters before publishing — a result that exists only at temp 0 is a result about temp 0.

## Phase 1 — capacity deletion (REAP)

| arm | source |
|---|---|
| base | `zai-org/GLM-4.7-Flash` (via unsloth GGUF) |
| pruned | `cerebras/GLM-4.7-Flash-REAP-23B-A3B` (via unsloth GGUF) |

One variable: expert count. Official Cerebras prune, so **no fine-tune confound** — this is why we
use GLM rather than the Qwen3.6-28B REAP everyone is running, which carries a LoRA rank-32 fine-tune
on 2,326 distilled reasoning traces stacked on top of the pruning and cannot attribute anything.

Run IKP T1–T4 and HumanEval+ on both arms.

## Phase 2 — precision reduction (quantization ladder)

Base: **Qwen3.6-27B BF16** (already on disk). All arms built locally from that one file with
identical flags, `--pure`, `--token-embedding-type` and `--output-tensor-type` pinned across arms
(§2).

Arms: `Q8_0` (reference) → `Q5_K_M` → `Q4_K_M` → `IQ4_XS` → `IQ3_XXS` → `IQ2_M`, plus `TQ4_1S` /
`TQ3_1S` for continuity with the Pulsar campaign. Go low enough to find the cliff; if IQ2_M is still
flat on IKP the thesis is in trouble and that is the point.

**bpw measured from tensor offsets** (`tensor_bpb.py`), never from the label.

VRAM note: 27B at Q4 ≈ 16 GB is tight on the 9070 XT and `Q8_0` ≈ 28 GB does not fit — take the top
anchor on `.194` once BFCL clears, or on CPU. Everything from Q5_K_M down runs on the control plane.

## The falsifier — stated before any run

The thesis requires **differential** degradation. Three outcomes kill it:

1. Both curves flat → compression is cheaper than anyone thought.
2. Both curves fall **together** → compression costs capability generally; nothing special about
   knowledge, and the field's panels are fine.
3. Reasoning falls *faster* than knowledge → thesis inverted.

Only "knowledge falls materially faster than reasoning, on the same arms" confirms it. Report the
gap as `Δknowledge − Δreasoning` in percentage points, not as two separate stories.

## Pre-registered predictions (§8)

Record these before the first arm runs; score every one afterwards, including falsifications.

| id | prediction | confidence |
|---|---|---|
| **P-R1** | REAP: IKP **T1** within ±2 pp of base | 0.75 |
| **P-R2** | REAP: IKP **T3+T4** combined drops ≥ 5 pp | 0.70 |
| **P-R3** | REAP: HumanEval+ within 2 pp of base | 0.80 |
| **P-Q1** | Quant: HumanEval+ flat (within 3 pp) down to 4 bpw | 0.75 |
| **P-Q2** | Quant: IKP T3+T4 drops ≥ 5 pp by 4 bpw | 0.60 |
| **P-Q3** | Quant: the knowledge/reasoning gap widens monotonically as bpw falls | 0.65 |
| **P-X1** | **Deletion hurts knowledge more than precision reduction does** at matched compression ratio — i.e. `Δknowledge − Δreasoning` is larger for Phase 1 than for the Phase 2 arm of equivalent size reduction | 0.65 |

P-X1 is the mechanistic claim and the one worth being wrong about publicly. P-Q2 is deliberately the
least confident: quantization degrades every weight a little, which is a gentler operation than
deleting an expert outright, so the knowledge cliff may sit lower than 4 bpw.

## K — the one open parameter

Left unresolved pending buun's answer on the determinism fix in his fork.

- If determinism is **confirmed on our hardware** (validate against the HA-04 reproducer, which was
  bistable 35 / 100 / 100 / 35 at temp 0 — require 5/5 identical), then **K = 1** is sufficient:
  greedy decode plus exact-match scoring, nothing left to vary.
- If **not confirmed**, §7 applies: **K ≥ 5**, report `n_observed / n_runs` per tier, and treat any
  single-run tier delta as an existence proof rather than a rate.

Do not start Phase 1 before K is fixed. Everything else in this spec is complete without it.

## Environment to record with every result (§9)

Build commit + branch + dirty flag; exact flags including `-ngl`, `-fa`, `-ctk`/`-ctv`, `-ub`; GPU
clock and power cap; node timezone (`.194` is UTC, control plane is EDT); `GGML_TQ_NATIVE` state for
any TQ arm; scored-question count per tier.

**KV cache must be held constant and stated.** Any KV quantization difference between arms
invalidates the comparison, and it is a separate axis from the one under test.

## Out of scope

- KV-cache quantization (its own axis; also makes numbers incomparable to full-precision-KV results).
- Long context, multilingual, agentic/tool-use.
- Absolute capability claims of any kind. This spec measures **deltas between arms only**.
- The Qwen3.6-28B REAP — LoRA confound, see Phase 1.

## Delegation (§11)

If any leg is run by another agent, the following must come back or the result is not accepted: the
raw artifact path; the G-3 grep and its count; `n_observed / n_runs` for any "no degradation" claim;
the §9 environment block; and which predictions were scored, including falsifications. A report of
"no significant degradation found" with no scored-count evidence fails the checklist by
construction — that string is exactly what a run scoring zero questions produces.

## Why this is publishable

- The knowledge/reasoning split under compression is asserted everywhere as folklore and measured
  nowhere with a tiered instrument.
- It reframes a whole genre of claim — "our 2-bit / pruned model matches the big one" — by naming the
  axis those claims are not tested on. Directly useful for auditing vendor panels.
- P-X1 distinguishes *two mechanisms* of compression rather than treating "smaller" as one thing.
- The method is reusable for any future compression technique, and the instrument already exists.
