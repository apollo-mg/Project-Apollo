# Pre-registration — does calibration composition govern the damage profile?

**Logged 2026-08-07, before any download and before any inference.** Commit timestamp is the record.

## The question this campaign has asserted but never tested

`RESULT_differential_knowledge_vs_code.md` found that 25 % expert pruning calibrated on
code/agentic data left code intact (+1.22 pp HumanEval+) and collapsed factual recall
(−36.8 pp committed accuracy), and named the mechanism: **REAP scores experts by router-gate ×
activation-norm over the calibration set, so experts that never fire on that set read as
low-saliency and are removed.** Cerebras calibrated on `evol-codealpaca` / `xlam-function-calling`
/ `SWE-smith-trajectories` — all code, none factual.

That is a *story* consistent with one observation. It has never been tested by varying the
calibration set, which is the only way to confirm it by contrast.

**0xSero's Qwen3.6-28B varies exactly that.**

| | Cerebras GLM-REAP | **0xSero Qwen3.6-28B** |
|---|---|---|
| calibration | evol-codealpaca, xlam-function-calling, SWE-smith — **code/agentic only** | 5,000 stratified samples: internal file (**general**, coding, reasoning) + `structured-outputs-calibration-v1` |
| expert rankings | fresh | **fresh** (`REAP observation` step on these weights) |
| prune ratio | 25 % | **20 %** |
| base | GLM-4.7-Flash | `Qwen/Qwen3.6-35B-A3B`, 40 layers, 256→205 experts/layer |
| published benchmarks | HumanEval / HumanEval+ only | **none — metrics table is `{{MMLU_BASE}}` placeholders** |

**He makes no retention claim.** The card's headline table is entirely unfilled template
placeholders. Search summaries describing "competitive quality across knowledge benchmarks" do
**not** reflect card text and are not treated as a claim here. This measures an artifact, it does
not contradict anyone.

## The confound, stated up front

**Ratio and calibration composition both differ (20 % vs 25 %).** A clean design would hold ratio
fixed. This one cannot, so a preserved-knowledge result is compatible with two readings:

1. general-inclusive calibration preserved the factual experts (the mechanism), or
2. 20 % is simply below whatever threshold breaks knowledge, independent of calibration.

The only argument distinguishing them from *this* pair is magnitude: a 5 pp ratio difference
explaining a ~37 pp swing would be a very steep dose-response. **That is an argument, not a
control.** The Akicou GLM ladder (09/19/39/50, one pruner, one base) is what actually resolves it —
if GLM at 19 % still collapses, ratio is excluded and calibration is confirmed. **This leg does not
settle the mechanism on its own and must not be written up as if it does.**

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-Q0** | **GATE** — base arm committed T1 accuracy ≥ 85 % (IKP discriminates on this family; GLM base was 93.5 %) | 0.75 |
| **P-Q1** | **HINGE** — pruned arm committed T1 accuracy is within **10 pp** of base, i.e. knowledge is preserved | 0.55 |
| **P-Q2** | pruned arm IKP refusal rate stays below **25 %** (GLM pruned hit 61.3 %) | 0.60 |
| **P-Q3** | **CONDITIONAL, only if P-Q1 holds** — the pruned arm does **not** show the C3 positional collapse (order sensitivity < 20 pp; GLM pruned was 59.1 pp) | 0.65 |

**P-Q0 gates everything.** If IKP cannot discriminate on Qwen3.6, no arm comparison is readable —
the same G-2 gate the GLM campaign ran before trusting any number.

**P-Q1 at 0.55 is deliberate.** I genuinely do not know. General data being *present* should protect
factual experts, but 5,000 stratified samples is a small calibration set and "general" is
unspecified — nominal inclusion is not the same as adequate coverage.

**P-Q3 is the one I care most about.** Today's C4/C5 work showed the contradiction collapse is
specific to the model's *own damaged prior* — it handles foreign contradictions nearly as well as
base (83.9 % vs 33.9 %). If knowledge is preserved here, the prior is not damaged, and the C3
defect should be absent. If it appears *anyway*, then pruning damages in-context adjudication
independently of knowledge, which would be a bigger and more troubling finding than anything so
far.

## Interpretation, fixed before the data

- **P-Q1 holds** → calibration composition is confirmed by contrast, subject to the ratio caveat.
  The campaign's headline becomes far more useful: *pruning is not inherently knowledge-destroying;
  code-only calibration is.* That is actionable for anyone producing REAPs.
- **P-Q1 fails** → knowledge collapses even with general data in the calibration set. The mechanism
  story is wrong or incomplete, and the honest conclusion is that expert pruning damages factual
  recall broadly regardless of what you calibrate on. This would **falsify the campaign's central
  explanation**, and it is the outcome worth publishing loudest.
- **P-Q0 fails** → diagnose the instrument on Qwen3.6 before reading anything else.

## Configuration, fixed in advance

Both arms from **0xSero** — the pruner packaged both GGUFs himself, so conversion tooling and
provenance are identical, which is what `PHASE0_GLM_REAP_PARITY` established for the GLM pair
(both unsloth).

| field | value |
|---|---|
| base arm | `0xSero/Qwen3.6-35B-GGUF` → `Qwen3.6-35B-A3B-Q6_K.gguf` (28.5 GB) |
| pruned arm | `0xSero/Qwen3.6-28B-GGUF` → `model.q6_k.gguf` (23.2 GB) |
| quant | **Q6_K on both**, matching the GLM campaign for cross-leg comparability |
| host | `.73`, 2×P100 @ 1063 MHz / 150 W; 61 GB free (51.7 GB needed) |
| server | `-c 4096 -ngl 99 -sm layer -np 1 --jinja`, fall back to Q5_K_M if 28.5 GB will not fit 32 GB VRAM |
| harness | `ikp_run.py` / `ikp_score.py` unmodified, `--no-think`, concurrency 1, `--max-tokens 64`, temp 0 |
| exclusions | `--exclude-source researcher`, identical both arms (as in every prior leg) |
| gates | G-1 packaging parity via `gguf_probe.py`; G-1a `expert_gating_func` asserted from each load log; G-5 2 pp `no_answer` divergence rule |

**K=1**, not reproducible on this fleet — existence proof, not rate. Gaps under ~5 pp are not to be
read as real without replication.
