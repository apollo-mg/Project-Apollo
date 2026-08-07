# Knowledge vs reasoning under compression — campaign synthesis

**Status as of 2026-08-07.** One model pair, one prune ratio, ten measured legs. This file is the
narrative; every number below is sourced to a receipt in this directory and none of it is restated
from memory. Read this first, then the receipt for whichever leg matters to you.

**Subject:** `GLM-4.7-Flash-Q6_K` (29.94 B) vs `GLM-4.7-Flash-REAP-23B-A3B-Q6_K` (23.00 B), both
unsloth, served on `.73` (2×Tesla P100 @ 1063 MHz / 150 W), build `tom_default`, temp 0, K=1.
REAP = router-gate × activation-norm expert pruning (Cerebras, arXiv 2510.13999); this pair drops
25 % of experts.

---

## The chain of findings

### 1. Pruning is differential, not uniform

| axis | instrument | base | pruned | Δ |
|---|---|---|---|---|
| **code** | HumanEval+ pass@1, 164 problems | 82.32 % | **83.54 %** | **+1.22 pp** |
| **knowledge** | IKP T1, accuracy among committed answers | 93.5 % | **56.7 %** | **−36.8 pp** |

The pruned model is marginally *better* at code and catastrophically worse at facts. Same two
GGUFs, same host, same harnesses, one structural difference.
→ `RESULT_differential_knowledge_vs_code.md`

### 2. The mechanism is the calibration set

Cerebras calibrated on `evol-codealpaca`, `xlam-function-calling`, `SWE-smith-trajectories` — all
code/agentic, none factual. REAP scores experts over that set, so experts that never fire on code
read as low-saliency and are removed.

Their retention claim — *"Retains all core functionalities including code generation, agentic
workflows, repository-scale understanding, and function calling"* — lists **only capabilities they
calibrated on.** It is accurate and it is not a claim about knowledge.

**The panel cannot see the damage, because the panel and the calibration set are the same thing.**
→ `RESULT_differential_knowledge_vs_code.md` §"Why"

### 3. Withdrawal dominates fabrication

Of the 486 probes the base answered correctly:

| becomes | n | share |
|---|---|---|
| still correct | 122 | 25 % |
| **refusal** | **260** | **54 %** |
| confidently wrong | 98 | 20 % |

Three-quarters of what it knew is gone, but most of the loss is *honest*. The model mostly knows it
doesn't know.
→ `ERROR_STRUCTURE_AND_HEALING.md`

### 4. The facts are demoted, not deleted

Teacher-forced gold rank, paired on identical probes:

| | confident errors (n=77) | refusals (n=60) |
|---|---|---|
| gold in top-10 at position 0 — base | 97 % | 95 % |
| gold in top-10 — **pruned** | 66 % | 40 % |
| gold still in top-100 — pruned | **95 %** | **88 %** |
| paired gold logprob worse under pruning | 61/61 | 45/46 |
| median delta | −1.50 nats/tok | −2.65 nats/tok |

At the answer slot the base holds gold at **rank 1, logprob ≈ −0.00** — certainty. Pruning moves it
to rank 14–61 and −2 to −6 nats. **Healing would be re-sharpening, not re-learning.**
→ `RESULT_PHEAL_gold_rank.md`

### 5. Retrieval fully rescues it — when uncontested

Population = the 358 probes the pruned arm lost, so its closed-book accuracy there is **0 % by
construction**.

| arm | C1 clean | C2 + 3 distractors | CTRL |
|---|---|---|---|
| base | 100 % | 100 % | 100 % |
| pruned | **100 %** | 99.7 % | 100 % |

Every fact it could no longer produce, it produces correctly when handed. `Fallingwater` goes from
*"Charles Ahrens."* to `Frank Lloyd Wright`.
→ `RESULT_RAG_ARM.md`

### 6. …but not when the context contradicts it

| arm | order | gold rate (committed) |
|---|---|---|
| base | gold 1st / 2nd | 100.0 % / 93.4 % |
| pruned | gold 1st / 2nd | 93.0 % / **33.9 %** |

```
ORDER SENSITIVITY    base 6.6 pp        pruned 59.1 pp
```

On GLM the base model picks gold wherever it sits and the pruned model largely picks whatever comes
first — at **every tier** (base 100.0/92.9/71.4, pruned 38.1/31.0/33.3), so this contrast is not a
population artifact.
→ `RESULT_C3_CONTRADICTION.md`

**Corrected 2026-08-07 — this does not generalize as originally stated.** Repeating C3 on Qwen
failed its own base-arm control: base order sensitivity **50.8 pp**, pruned 62.7 pp, so P-QX2 was
left **unscored** rather than claimed. The unifying variable is not pruning but **prior strength** —
a model overrules a contradictory entry where it knows the fact well and follows position where it
does not (Qwen base: T1 85.7 %, T2 83.8 %, T3 22.0 %, T4 23.7 %). Pruning degrades this *by
weakening the prior*, so the defect's tier profile follows the closed-book damage profile in each
model: uniform in GLM, concentrated at T2 (−20.2 pp) in Qwen.
→ `RESULT_QWEN_CONTEXT.md`

### 7. Provenance redirects the failure, it doesn't fix it

| | C4a (authority on gold) | C4b (authority on the confabulation) |
|---|---|---|
| base | 96.7 % | 76.5 % |
| pruned | 87.9 % | **44.6 %** |

Tagging gold authoritative lifts the pruned arm from 33.9 % → 87.9 %, which looks like a cheap fix.
Move the tag onto the confabulation and it drops below chance. **It swapped position-following for
tag-following** — worse, because position is an accident of retrieval order while a source label is
adversarially controllable.

**The base arm refused 34/68 on C4b; the pruned arm 12.** Handed an authoritative source that
contradicts what it knows, the base model declines. The pruned model complies. *Detecting the
conflict is itself a capability, and pruning cost it.*
→ `RESULT_C4_C5.md`

### 8. Whose wrong answer competes also matters (GLM)

Identical layout, gold second, only the competing entry differs:

```
competing entry = its OWN confabulation      ->  33.9 %
competing entry = another probe's gold       ->  83.9 %
```

50 pp from swapping the distractor; base untouched either way. On GLM the collapse is worst when the
competing entry is what the model would have said itself — **exactly when retrieval is correcting
it.** Untested on Qwen.
→ `RESULT_C4_C5.md`

### The effect, bounded

| condition | pruned behaviour |
|---|---|
| 1 correct entry + 3 unrelated (C2) | 100 / 100 / 99.1 / 100 % across all 4 positions — position irrelevant |
| gold vs a foreign wrong answer (C5) | 98.4 / 83.9 % — mild |
| gold vs **its own confabulation** (C3) | 93.0 / **33.9 %** — collapse |
| same, provenance-tagged (C4) | 87.9 / **44.6 %** — follows the tag |

Not primacy bias — C2 shows position is irrelevant when nothing contradicts.

### Reconciling §6 §7 §8 — two mechanisms, not one

§6's correction displaced the single-mechanism story, so the three sections must be read together:

| governs | mechanism | evidence | status |
|---|---|---|---|
| **how hard the model fights** for the retrieved fact | **prior strength** — strong prior overrules a contradictory entry, weak prior follows position | Qwen tier gradient 85.7 / 83.8 / 22.0 / 23.7 %; GLM confirms at T1/T2 only (T3 n=7, T4 n=1) | replaces the pruning-specific framing |
| **whether the competing entry is a contender at all** | **own-vs-foreign** — a foreign wrong answer is rejectable on *relevance* grounds the model's own confabulation is not | GLM C3 33.9 % vs C5 83.9 %, base unmoved either way | GLM only, **open** |
| **what the model substitutes when it stops adjudicating** | position, or a **source label** if one is offered — and it prefers the label | GLM C4b 44.6 %, below its own position-following rate | GLM only, **open** |

Prior strength does **not** explain C4b or C5; those need the second and third rows. Pruning enters
only through the first — it weakens the prior. Nothing in the campaign yet shows pruning creating a
failure mode that stock models lack, and §6 shows a stock model exhibiting the position failure on
its own weakly-known facts.

The C4/C5 rows are **single-model results on GLM** and were never repeated on Qwen. Until they are,
"pruned models follow source labels" is a GLM observation, not a campaign claim.

---

## What the campaign is entitled to claim

> Expert pruning leaves code intact and substantially damages closed-book factual recall — 36.8 pp
> on GLM at 25 %, 31.4 pp on Qwen at 20 % — across two calibration recipes, so a broader calibration
> set does not prevent it. Retrieval-grounded answering is unimpaired **so long as the retrieved
> context is uncontested** (100 % on both arms of both pairs). Where retrieval surfaces an entry
> that contradicts the model, adjudication degrades in proportion to how weakly the model holds the
> fact — and pruning weakens it. On GLM, at 25 % and damaged uniformly, that degradation is total
> (93.4 → 33.9 %).

Practically: **not knowledge stores; usable with retrieval; least reliable exactly where retrieval
is correcting them.** Real pipelines return conflicting chunks routinely.

**The pruning-specific reading is retired.** Contradiction fragility is not something pruning
introduces — stock `Qwen3.6-35B-A3B` has it on its own weakly-known facts. Pruning moves a model
further down a curve every model is already on.

## What it is not entitled to claim

- **The mechanism claim is FALSIFIED in its strong form** (2026-08-07). Varying the calibration set
  did not preserve knowledge: `0xSero/Qwen3.6-28B-REAP20`, calibrated on general+coding+reasoning
  with fresh rankings at a *lower* 20 % ratio, still lost **−16.1 pp on T1 and −31.4 pp overall**.
  What survives is only that code-only calibration explains why *Cerebras's panel could not see*
  their damage — not the damage itself. See `RESULT_QWEN_CALIBRATION_CONTRAST.md`.
- **Failure mode is not consistent across models.** GLM-REAP **withdrew** (refusal 12.7 % → 61.3 %);
  Qwen-REAP **fabricates** (refusal 1.1 % → 11.9 %, WRONG 15.8 % → 31.8 %). The less aggressively
  pruned model with the broader calibration set is the more dangerous artifact.
- **Tail-selectivity is open, not settled.** Damage was uniform across tiers on GLM (falsifying
  P-X1) and graded by obscurity on Qwen (T1 −16 → T3 −43). Whatever governs that is not the
  calibration set.
- **The contradiction collapse is not pruning-specific.** `RESULT_QWEN_CONTEXT.md` (2026-08-07)
  falsified the P-QX1 gate: base Qwen3.6-35B is itself 50.8 pp order-sensitive, and fails to
  reproduce a fact it answered correctly closed-book in **53 % of these pairs** when a contradicting
  entry is placed first. **That number is an upper bound, not an estimate** — the two entries are
  degenerate duplicates (identical stems, differing only in answer value), so position is the only
  residual signal, which maximizes the effect; and "answered correctly" is K=1 on a fleet with
  documented temp-0 bistability. Pruning's
  own contribution, tier-matched, is −11.1 pp overall and −20.2 pp at T2. The C3 populations were
  **not tier-matched across models** — a design defect, since the population is "base right, pruned
  wrong" and therefore inherits each model's damage profile. Cross-model contradiction claims need
  a stratified re-run.
- **Retrieval rescue of uncontested facts is the one thing that has replicated cleanly** — 100 % on
  both arms of both model pairs (`RESULT_RAG_ARM.md`, `RESULT_QWEN_CONTEXT.md` C1, 199/199 each).
- **One pair, one ratio, one pruner.** No dose-response. The Akicou GLM ladder (09/19/39/50) is the
  designed experiment for that and has not run.
- **K=1 throughout**, and temp-0 is not reproducible on this fleet (`DETERMINISM_TEMP0_GLM_P100.md`).
  Every result is an existence proof, not a rate.
- **Nothing about other pruning methods, or about quantization**, whose mechanism-vs-mechanism
  comparison (P-X1) remains open.

---

## Methodology — the confounds caught, and the ones that cost us

This campaign's results are only worth what its error-catching is worth, so:

| what | outcome |
|---|---|
| **Mode confound** | Thinking-off cost the pruned arm 53 refusals/145 vs base's 5. The first −56 pp T1 result was scaffold-dependence + knowledge, inseparable. **Retracted before publication**; replaced with committed-error rate. → `PHASE1_MODE_CONFOUND.md` |
| **Fail-green** | `PREAMBLE` imported numpy, `.73` had none, so correct solutions scored 0.00. Would have produced 0 % vs 0 % and scored the hinge prediction HELD from two zeros. Caught; `preflight()` now aborts unless the grader passes a canonical solution first. |
| **Grader-artifact symmetry** | The pruned arm clips to surnames (`"Kepler."`), which the grader books WRONG. If asymmetric, part of the −36.8 pp would be style. Checked per arm: ~5 true artifacts each, 0.8 pp differential. **Headline survived.** |
| **Ceiling with no sensitivity** | C2 scored 100 % on *both* arms, so it never demonstrated power to discriminate — recorded as such rather than presented as a clean pass, and C3 was built to have teeth. |
| **Instrument gate** | G-1a: a GGUF omitting `expert_gating_func` is resolved by a hardcoded heuristic, so two arms can silently run different gating. Asserted from the runtime's own `print_info` before every run. |

**Falsifications, kept:**

- **P-X1** — damage would concentrate in the tail. **FALSIFIED**: broad and roughly uniform
  (+33–48 pp across T1–T4). The criterion is not *rare*, it is *does not activate on code*.
- **P-H2** — our absolute HumanEval+ would replicate Cerebras's 89.0. **FALSIFIED** (82.32 / 83.54),
  which gated P-H1 out of scoring entirely.
- **P-HEAL1/2** — I predicted refusals would be the recoverable bucket and confident errors the lost
  one. **Backwards**: the 0.35-confidence prediction held, the 0.60 one failed.
- **P-C5** — I predicted general contradiction-adjudication failure. **FALSIFIED**, and the
  falsification is what confirmed the own-prior framing.
- **A withdrawn result**: "the refusal beats gold by 3.02 nats" was dropped mid-analysis on noticing
  the IKP system message *instructs* the refusal. The paired base-vs-pruned delta survives because
  priming cancels across arms.
- **A loose bound corrected**: `ERROR_STRUCTURE_AND_HEALING.md` §3 called 83 % "shares no token with
  the gold" an upper bound on *the fact is gone*. The logits put gold in the top-100 for 95 % of
  those same cases. Token-space absence is not weight-space absence.

## Receipt index

| leg | file |
|---|---|
| Phase-0 packaging + gating parity | `PHASE0_GLM_REAP_PARITY.md` |
| Instrument discrimination (G-2) | `G2_IKP_INSTRUMENT_CHECK.md` |
| Determinism → K=5 justification | `DETERMINISM_TEMP0_GLM_P100.md` |
| Mode confound (retraction) | `PHASE1_MODE_CONFOUND.md` |
| Committed-error result | `PHASE1_RESULT_COMMITTED_ERROR.md` |
| HumanEval+ prereg / result | `PREREG_HUMANEVAL_ARM.md`, `RESULT_differential_knowledge_vs_code.md` |
| Error structure + healing hypothesis | `ERROR_STRUCTURE_AND_HEALING.md` |
| Gold-rank forced decode | `RESULT_PHEAL_gold_rank.md` |
| RAG prereg / result | `PREREG_RAG_ARM.md`, `RESULT_RAG_ARM.md` |
| Contradiction prereg / result | `PREREG_C3_CONTRADICTION.md`, `RESULT_C3_CONTRADICTION.md` |
| Provenance + foreign contradiction | `PREREG_C4_C5.md`, `RESULT_C4_C5.md` |
| Calibration contrast | `PREREG_QWEN_CALIBRATION_CONTRAST.md`, `RESULT_QWEN_CALIBRATION_CONTRAST.md` |
| Qwen context arms (C1 + C3) | `PREREG_QWEN_CONTEXT.md`, `RESULT_QWEN_CONTEXT.md` |
| DS4-Flash K160 (deferred, 4 confounds) | `PREREG_DS4_K160.md` |
