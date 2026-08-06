# Protocol — Mode-Recovery Evaluation for Reasoning Models

**Status:** v1, with a completed worked example (Laguna-S-2.1, HumanEval+, 2026-07-24/25).
**Problem it solves:** a reasoning model evaluated in ONE mode produces a number that is not the
model's capability *and* not its deployment behaviour — it is an artifact of the harness/mode pairing.
Single-mode evals systematically mis-attribute *mode faults* to *model limitations*.

## Why this exists (the recurring failure)

Repeatedly observed in this lab: a reasoning model + one off-spec harness setting = a false negative
that reads as a quant or capability limit.
- Bit Laguna v1: an "86%" that was a truncation mirage.
- Laguna temp-0 HumanEval+: "84.8%, 17 truncations" → mostly a **greedy-decoding artifact**; the same
  model/quant scores **90.85%** at its sampling temp.
- AgentWorld: a "blind spot" that was a 2048-token output cap, not a model failure.

The fix is not "pick the right mode once." It is to **treat mode as an axis of the experiment** and
report the axis, because *which* mode wins is not predictable in advance (see falsified prediction below).

## The protocol

### 1. Enumerate modes from the model's own artifacts — don't hardcode
Read the chat template for boolean switches rather than maintaining a list:
```bash
curl -s http://HOST:PORT/props | python3 -c "import sys,json;print(json.load(sys.stdin)['chat_template'])" \
  | grep -oE '(enable_thinking|preserve_thinking|[a-z_]*think[a-z_]*)\s*\|\s*default\([a-z]+\)'
```
Laguna's `laguna_glm_thinking_v8` exposes `enable_thinking | default(true)` and
`preserve_thinking | default(false)`. Flip via the request body, no reload:
`"chat_template_kwargs": {"enable_thinking": false}`.

**Exclude inert modes.** `preserve_thinking` governs retention of *prior-turn* reasoning; on a
single-turn benchmark there is no prior turn, so it is a no-op here. Do not pad the matrix with modes
that cannot act on the task shape.

### 2. Preflight every mode before committing a multi-hour run
A silently-ignored flag yields data labelled as a mode it never ran in — worse than no data.
Gate the run on a one-request proof (`preflight_nothink.py`): mode is only confirmed when
`reasoning_content` is empty, the answer arrived in `content`, and `finish_reason != "length"`.
**A failed preflight must abort the run, not warn.**

### 3. Run K≥3 per mode, full set
At temp>0 one pass is one sample. K≥3 separates *stochastic* misses from *mode* faults and yields the
consistency map. Report pooled pass@1 **and** per-sweep mean±std.

### 4. Re-test failures in every other mode (`HEP_ONLY` accepts the failing task_ids)
Cheap: only the misses are re-run. This is the recovery step.

### 5. Report three numbers, never one
| Number | Meaning | Use |
|---|---|---|
| **Per-mode pass@1** | what you get if you deploy in that mode | the honest headline |
| **Best-of-modes envelope** | ceiling if each problem were routed to its best mode | capability claim ONLY — never a deployment number |
| **Recovery matrix** | per task_id × mode → bucket | separates genuine gaps from mode artifacts |

**Rule:** a failure that recovers in another mode may never be laundered into a single-mode headline.
The gap between per-mode and envelope *is* the mode-selection value, and must be labelled as such.

### 6. Record cost, not just accuracy
Output tokens and wall-clock per mode. An accuracy win bought with 8× compute is a different
engineering decision from a free one.

### 7. Provenance
Record the mode state **in the results artifact itself**. (Lesson: Run A below was launched before the
harness recorded `enable_thinking`; its JSON says `null`, and its mode is only established by a
`/proc/<pid>/environ` read. Recoverable here, unrecoverable if the process had exited.)

---

## Worked example — Laguna-S-2.1-UD-Q2_K_XL, HumanEval+ (full 164, K=3)

Same model, same quant, same 164 problems, same server. One axis changed: thinking.
Run A = thinking ON @ temp 0.7/top_p 0.95/top_k 20 (creator sampling params).
Run B = thinking OFF @ temp 0.6 (Tom/offlabel deployment recommendation for coding).

| | Run A (think ON) | Run B (think OFF) |
|---|---|---|
| pooled pass@1 | **90.85%** (447/492) | **88.21%** (434/492) |
| per-sweep | 90.85% ± **0.50%** | 88.21% ± **1.52%** |
| PASS / WRONG | 447 / 30 | 434 / 56 |
| **TRUNCATED** | **10** (+1 NO_ANSWER) | **0** |
| consistency (of 164) | 143 all · 10 never · **11 flaky** | 131 all · 9 never · **24 flaky** |
| output tokens | 1,457,555 | 173,957 (**8.4× less**) |
| wall-clock | 20.15 h | 2.53 h (**8.0× faster**) |

### Recovery matrix (A × B, per problem)
```
   A(think-ON) x B(think-OFF)  count
        ALL x ALL               123
        ALL x FLAKY              16     thinking-OFF destabilised
      FLAKY x ALL                 6     thinking-OFF stabilised
      FLAKY x FLAKY               5
       NONE x NONE                5     <- genuine capability gaps
        ALL x NONE                4     thinking REQUIRED
       NONE x FLAKY               3
       NONE x ALL                 2     thinking HARMFUL
```
- **Genuine gaps: only 5/164** — `HumanEval/32, 91, 132, 145, 163` fail in *both* modes.
- **Thinking hurt** on 5 problems (0 in A, solvable in B): `55, 76, 86, 116, 134`.
- **Thinking helped** on 4 problems (0 in B, solvable in A): `83, 102, 127, 130`.
- **Best-of-modes envelope: 159/164 = 97.0%** vs single-mode best 90.85% — **6.2 points are hiding in
  mode selection alone.** That gap is the protocol's entire justification.

### A's truncation cases under thinking-OFF (the decisive sub-test)
```
HumanEval/44   P,P,T (0.67) -> P,P,P (1.00)
HumanEval/76   T,E,W (0.00) -> W,W,P (0.33)
HumanEval/90   P,T,P (0.67) -> P,P,P (1.00)
HumanEval/116  T,T,W (0.00) -> P,P,P (1.00)
HumanEval/118  T,P,T (0.33) -> W,P,P (0.67)
HumanEval/132  W,W,T (0.00) -> W,W,W (0.00)
HumanEval/145  W,T,T (0.00) -> W,W,W (0.00)
```
5/7 improved; **truncation as a failure class disappears entirely** (10 → 0).

## Findings

1. **Logged prediction FALSIFIED.** Predicted thinking-OFF would *beat* thinking-ON. It **lost by 2.64
   points** (88.21 vs 90.85). The sub-prediction held: truncations are purely a thinking-mode artifact
   (10 → 0), and coherent-but-wrong misses mostly persisted (`132`, `145` stayed WRONG in both).
2. **The thinking tax is a cost story, not an accuracy story.** +2.64 points costs **8.4× tokens and
   8× wall-clock**. For most deployments that is a losing trade; for a leaderboard number it is not.
3. **Thinking buys consistency.** Flaky problems 11 → 24 and sweep std 0.50% → 1.52% with thinking OFF.
   Thinking's real product here is *variance reduction*, which a pass@1 headline hides.
4. **Scope-check against the external claim.** Tom/offlabel reports Laguna's thinking as
   "net-negative on work it hasn't seen" (a 30-turn agent probe wedged 91 min with thinking ON;
   30/30 with it OFF). On **single-turn HumanEval+ pass@1 that does not reproduce** — thinking is
   net-*positive* by 2.64 points. What *does* reproduce is the **hang/loop failure mode** (all 10
   truncations are thinking-ON). Most likely reconciliation: the defect is multi-turn/agentic
   accumulation, not per-problem reasoning quality. **Untested here; stated as a hypothesis.**
   Tom's separate "integrity blind spot" axis is **not** touched by this data.
5. **Only 3% of HumanEval+ is a genuine wall for this model+quant.** The rest is mode/sampling
   sensitivity — which is a statement about *harness design*, not about Laguna.

## Companion: model-shipped harness config (proposed)

This protocol has to *discover* modes by grepping jinja and reading a third party's blog post. What is
missing upstream is a conditional declaration shipped with the model — flat `generation_config.json`
cannot express "if task=code ∧ multi-turn → thinking OFF, temp 0.6". A small conditional matrix
(`if <task-shape> → {params}`, `else …`) that harnesses parse would have told this harness
"Laguna + coding → thinking OFF" without reverse-engineering. Candidate delegation to Gemini:
schema + reference parser.

## Reproduce
```bash
# Run A (thinking ON)
HEP_MODEL=<label> HEP_ENDPOINT=http://HOST:PORT/v1/chat/completions \
HEP_TEMP=0.7 HEP_TOP_P=0.95 HEP_TOP_K=20 HEP_K=3 HEP_TAG=t07_k3 hep_eval.py
# Run B (thinking OFF) — preflight first, abort on failure
preflight_nothink.py || exit 2
HEP_THINK=0 HEP_TEMP=0.6 HEP_TOP_P=0.95 HEP_TOP_K=20 HEP_K=3 HEP_TAG=t06_k3_nothink hep_eval.py
```
Artifacts: `laguna_hep_results_t07_k3.json`, `laguna_hep_results_t06_k3_nothink.json`
(scratchpad of session 9457b3f4; harness `hep_eval.py` carries the `HEP_THINK` switch).
