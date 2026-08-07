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

The base model picks gold wherever it sits. **The pruned model largely picks whatever comes first.**
→ `RESULT_C3_CONTRADICTION.md`

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

### 8. The failure is specific to its own prior

Identical layout, gold second, only the competing entry differs:

```
competing entry = its OWN confabulation      ->  33.9 %
competing entry = another probe's gold       ->  83.9 %
```

50 pp from swapping the distractor; base untouched either way. It is **not** general contradiction
failure — it fails when the competing entry is what it would have said itself, i.e. **exactly when
retrieval is correcting it.** The worst possible selectivity.
→ `RESULT_C4_C5.md`

### The effect, bounded

| condition | pruned behaviour |
|---|---|
| 1 correct entry + 3 unrelated (C2) | 100 / 100 / 99.1 / 100 % across all 4 positions — position irrelevant |
| gold vs a foreign wrong answer (C5) | 98.4 / 83.9 % — mild |
| gold vs **its own confabulation** (C3) | 93.0 / **33.9 %** — collapse |
| same, provenance-tagged (C4) | 87.9 / **44.6 %** — follows the tag |

Not primacy bias. Not general contradiction failure. **A specific inability to prefer a retrieved
fact over its own damaged prior, which a source label redirects rather than repairs.**

---

## What the campaign is entitled to claim

> 25 % expert pruning calibrated on code leaves code intact, collapses closed-book factual recall
> by 36.8 pp, and leaves retrieval-grounded answering unimpaired **so long as the retrieved context
> is uncontested.** Where retrieval surfaces a fact that contradicts what the pruned model would
> have said, it stops adjudicating on content and falls back on position or on source labels.

Practically: **not knowledge stores; usable with retrieval; fragile exactly where retrieval is
correcting them.** Real pipelines return conflicting chunks routinely.

## What it is not entitled to claim

- **The mechanism is unconfirmed.** "Calibration composition governs the damage profile" rests on
  one observation. Testing it requires *varying* the calibration set — in progress, see
  `PREREG_QWEN_CALIBRATION_CONTRAST.md`.
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
| Calibration contrast (in progress) | `PREREG_QWEN_CALIBRATION_CONTRAST.md` |
| DS4-Flash K160 (deferred, 4 confounds) | `PREREG_DS4_K160.md` |
