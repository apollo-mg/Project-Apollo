# Pre-registration — does the contradiction collapse generalize to a *fabricating* pruned model?

**Logged 2026-08-07, before any context-arm inference on either Qwen arm.** Probes built and
inspected first; no model has seen them.

## Why this is the right next question

`RESULT_QWEN_CALIBRATION_CONTRAST.md` established that the two pruned models fail in **opposite
modes**:

| of base-correct probes | GLM-REAP 25 % | **Qwen-REAP 20 %** |
|---|---|---|
| still correct | 25 % | **56 %** |
| → refusal | **54 %** | 9 % |
| → confidently wrong | 20 % | **27 %** |

GLM **withdrew**. Qwen **fabricates**, and retains twice as much.

`RESULT_C4_C5.md` found GLM's contradiction collapse is **specific to its own damaged prior** —
33.9 % when the competing entry is its own confabulation vs 83.9 % when it is a foreign wrong
answer, with base unaffected either way (0.0 pp order sensitivity). The proposed mechanism was
an inability to prefer a retrieved fact over what it would have said itself.

**Qwen is the natural test of that mechanism.** Its prior is damaged *differently* — wrong rather
than absent. If the collapse is about competing with a damaged prior, it should appear here too.
If it was really a property of the withdrawal mode, it should not.

## Design

Reusing the GLM builders unmodified, so the instruments are identical across models.

| cond | n | content |
|---|---|---|
| **C1** | 199 | clean context, one correct Q→A entry. Population = probes base got right and pruned LOST (150 WRONG + 49 REFUSAL), so pruned closed-book accuracy is **0 % by construction** |
| **C3a** | 131 | gold **first**, the model's own bare confabulation second |
| **C3b** | 131 | same pair, **order reversed** |

131 of 150 CORRECT→WRONG items reduce to a clean bare-answer span; the other 19 are dropped rather
than patched. Shape parity enforced (both entries bare spans) — a first GLM build paired `Ottawa`
against `"The capital of Canada is Toronto"`, which the model could separate by *form* instead of
content and score well for the wrong reason.

Both arms run everything. K=1, temp 0, `--no-think`, `--exclude-source researcher`, Q6_K,
mradermacher packaging both arms, `.73` 2×P100.

## Predictions (§8)

| id | prediction | confidence |
|---|---|---|
| **P-QX0** | **GATE** — pruned C1 ≥ 90 %: it can use *uncontested* context at all | 0.80 |
| **P-QX1** | **GATE** — base C3 order sensitivity ≤ 20 pp (base decides on content, as on GLM) | 0.75 |
| **P-QX2** | **HINGE** — pruned C3 order sensitivity ≥ 30 pp, i.e. the collapse generalizes (GLM: 59.1 pp) | 0.55 |

**P-QX0 gates everything.** If the pruned model cannot use clean context, C3 is unreadable and the
finding is a much bigger one about in-context grounding. **P-QX1** is the same control that made
GLM's C3 interpretable — without it an arm gap is unattributable.

**P-QX2 at 0.55 is honest uncertainty.** For: the C3 population is exactly where Qwen's prior is
wrong, which is the condition the mechanism names. Against: Qwen retains far more knowledge overall
and its damage is graded by obscurity rather than uniform, so its priors may be weaker competitors.

## Interpretation, fixed before the data

- **P-QX2 holds** → the contradiction collapse is a property of pruning-damaged priors generally,
  across two models, two pruners, two ratios, and two opposite failure modes. That makes it the
  campaign's most robust finding — and the most consequential, since retrieval is precisely the
  mitigation people reach for.
- **P-QX2 fails** → the collapse tracked GLM's *withdrawal* mode, not pruning as such.
  `RESULT_C3_CONTRADICTION.md`'s framing narrows to "pruned models that lose confidence", and the
  practical warning applies to some pruned models rather than all.
- **P-QX0 fails** → stop and diagnose; a pruned model that cannot use clean context is a larger
  result than anything about contradiction.

Either outcome is publishable. Only one extends the C3 finding.
