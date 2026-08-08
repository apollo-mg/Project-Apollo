# Result — the same flag does opposite things on the two arms; a bounded budget rescues both

**COMPLETE.** 11 cells — the 6 pre-registered, plus 5 added after the fact and labelled as such:
four cells at `max_tokens 4096` — two Bonsai (Finding 3, removing a confound in the original
design) and two Gemma (Finding 5) — plus one Gemma MTP-on cell (Finding 4). Pre-registered in
`PREREG_REASONING_BUDGET_SMOKE.md`, logged before any inference; the five additions are
**post-hoc and carry no pre-registered prediction.** The Headline table below is the
pre-registered `max_tokens 2048` design; Findings 3 and 5 carry their own 4096 tables.

**Date:** 2026-08-08. RX 9070 XT 16GB (gfx1201), stock clocks. Bonsai-27B Q2_g64 (7.59 GB) on
`engines/llama_cpp_bonsai/build_hip` `-c 32768`; Gemma-4-12B QAT UD-Q4_K_XL (6.72 GB) on
`engines/llama_cpp_turboquant/build_rocm` `-c 16384`, **MTP off** (declared deviation). Both
`-ngl 99 -fa on` fp16 KV, `--jinja --reasoning-format deepseek`, temp 0 / top_k 1,
`max_tokens 2048`, 8 most-constrained IFEval prompts of the panel's 541.

## Headline

| model | budget | w/reasoning | **w/answer** | mean reason ch | mean tok | cap | stop |
|---|---|---|---|---|---|---|---|
| **Bonsai** | −1 | 8/8 | **0/8** | 8263 | 2048 | 8 | 0 |
| **Bonsai** | **0** | 8/8 | **0/8** | 8263 | 2048 | 8 | 0 |
| **Bonsai** | **1024** | 8/8 | **8/8** | 4150 | 1617 | 3 | 5 |
| **Gemma** | −1 | 8/8 | **2/8** | 7806 | 2014 | 6 | 2 |
| **Gemma** | **0** | **0/8** | **8/8** | 0 | 518 | 1 | 7 |
| **Gemma** | **1024** | 8/8 | **8/8** | 4105 | 1321 | 0 | 8 |

```
answers delivered      -1        0       1024
  Bonsai              0/8      0/8       8/8
  Gemma               2/8      8/8       8/8
```

## Finding 1 — `--reasoning-budget 0` is model-dependent, and the template is the discriminator

- **Bonsai: INERT.** Budget-0 output is **byte-identical** to unrestricted — 0 differing fields
  across 8 responses × 11 fields, and identical generated text 8/8. The flag does nothing.
- **Gemma: LIVE.** 58 differing fields; reasoning collapses 8/8 → **0/8**, answers rise 2/8 → 8/8,
  mean tokens 2014 → 518.

Same flag, same server family, opposite outcomes. `0` means "immediate end", which needs the
chat template to expose a no-think path. Gemma's boot log prints `chat template, thinking = 1`;
Bonsai ships a ChatML-style template with `reasoning_mode: TAG_BASED` (`<think>`/`</think>`) and
no such path, so the request silently no-ops. **A flag being accepted on the command line is not
evidence it did anything** — the same lesson as [[gguf-label-is-not-a-spec]], one layer up.

## Finding 2 — `N>0` works on both, and is enforced precisely

| model | mean reason ch, −1 → 1024 | est. reasoning tokens at bound | budget |
|---|---|---|---|
| Bonsai | 8263 → 4150 | **~1037** | 1024 |
| Gemma | 7806 → 4105 | **~1026** | 1024 |

Two models, two builds, two templates, both landing within **~1.3 %** of the requested budget.
The agreement is the cross-check: chars ÷ 4 is a crude token estimator, and it would not
coincidentally produce ~1024 twice. Answers recover on both (0/8 → 8/8 and 2/8 → 8/8), and
Gemma reaches **8/8 `finish=stop`** — no truncation at all.

## Finding 3 — at the panel's own budget, you cannot fix Bonsai by raising `max_gen_toks`

The 2048 cells above have a confound: with all 2048 tokens eaten by reasoning, capping thinking
at 1024 mechanically frees ~1000 tokens, so 0/8 → 8/8 is partly arithmetic. Two extra Bonsai
cells at the panel's **`max_tokens 4096`** separate the flag from the arithmetic:

| Bonsai @ 4096 | w/answer | mean reason ch | mean tok | cap | stop |
|---|---|---|---|---|---|
| budget **−1** | **3/8** | 13992 | 3618 | 5 | 3 |
| budget **1024** | **8/8** | 4150 | 2074 | **0** | **8** |

**Doubling the ceiling does not help — Bonsai simply thinks twice as long.** Mean reasoning goes
8263 chars @2048 → **13992 @4096** (+69 %), and 5 of 8 still die at the cap with zero answer. The
model expands its deliberation to consume whatever it is given.

Meanwhile the bound is *ceiling-independent*: mean reasoning at budget 1024 is **4150 chars at
both** `max_tokens` 2048 and 4096 — identical. The cap acts on thinking, not on the ceiling.

**So the rescue is not an artifact of the halved budget.** At the panel's own 4096, unbounded
Bonsai delivers 3/8 and bounded Bonsai delivers 8/8 with zero truncation. The operational claim
for the article: **raising `max_gen_toks` will not fix Bonsai's empties; only a reasoning bound
will.**

## Finding 4 — the bound survives MTP (the panel's Gemma serving config)

Gemma budget 1024, **MTP on** (`--spec-type draft-mtp`, `--spec-draft-n-max 3`), same 8 prompts,
same `max_tokens 2048`:

| Gemma @ budget 1024 | w/answer | mean reason ch | mean tok | stop | decode |
|---|---|---|---|---|---|
| MTP **off** | 8/8 | 4105 | 1321 | 8/8 | 59.4 t/s |
| MTP **on** | 8/8 | 4451 | 1334 | 8/8 | **86.8 t/s** |

The drafter interacts cleanly with server-side `</think>` injection — bound held, answers held,
no truncation. The +8 % reasoning-char difference is within MTP's documented
lossless-in-distribution nondeterminism (panel caveat, receipted 2026-07-17).

**Provenance note, because the log looks alarming:** the MTP boot log emits
`W [spec] failed to measure draft model memory: failed to create llama_context from model`, and
this build exposes no draft-acceptance counter. The drafter was active regardless, on two
independent signals:

1. **Primary — output divergence.** At temp 0 / top_k 1 an undrafted run must reproduce the
   MTP-off baseline exactly. **0/8 responses were text-identical.** Only the drafter's
   documented lossless-in-distribution nondeterminism explains that.
2. **Corroborating — throughput.** 86.8 vs 59.4 t/s ≈ **1.46×**. Weaker evidence than (1): it
   compares wall-clock across two separately-launched servers with load time estimated from
   console timestamps, not instrumented.

That warning is therefore a non-fatal sizing probe, not a failed drafter. **The 1.46× is well
below the panel's receipted 110–143 t/s for MTP-on Gemma** — most likely because these
responses are dominated by reasoning text, which drafts poorly compared to the panel's mixed
generation, but that is an untested explanation and the gap is left open rather than papered over.

## Finding 5 — ⚠ the panel's Gemma mechanism does NOT reproduce on this instrument

`Battle16GB_Results.md` states: *"Gemma fails by thinking, then going silent — **zero** budget-cap
hits in the entire v2 run; she closes reasoning and EOSes without emitting an answer."* The
matched 2×2 at the panel's own `max_tokens 4096` says otherwise:

| @ 4096 | budget −1: answers | cap-death | **silent closure** | budget 1024: answers |
|---|---|---|---|---|
| **Bonsai** | 3/8 | 5/8 | **0/8** | 8/8 |
| **Gemma** | 3/8 | 5/8 | **0/8** | 8/8 |

**The two arms are indistinguishable.** Both deliver 3/8 unbounded, both cap-die 5/8, both reach
8/8 under a 1024 bound.

And the silent-closure signature — `finish_reason=stop` with an empty answer — **occurs zero
times in all 88 responses across all 11 cells.** Not rare: absent.

So on this instrument Gemma's failure is *cap-death, identical to Bonsai's*, and the asymmetry
the article's mechanism section is built on is not visible.

**This is a discrepancy, not a refutation.** Candidate explanations, none tested:

1. **Prompt subset.** These are the 8 *most-constrained* of the 541. The panel's claim was a rate
   over all 541. But "zero" admits no exceptions, and these 8 are members of that set — so the
   claims are in direct tension unless (2) or (3) holds.
2. **Serving path.** The panel drove Gemma through lm-eval-harness with `--apply_chat_template`
   and MTP on. This leg posts to `/v1/chat/completions` with `--jinja --reasoning-format deepseek`.
   A different template-application path can change thinking length.
3. **What was counted.** The panel graded answer text after the reasoning parser split
   `reasoning_content`; "empty response" there may not be the same event as `finish_reason` here.

**Why this needs resolving before publication:** the panel's per-prompt receipts were lost to the
scratchpad wipe (see [[scratchpad-is-volatile]]), so the "zero budget-cap hits" claim **cannot be
re-checked against its own evidence**. An external reader running the obvious check would land
where this leg landed. Cheapest resolution: re-run a handful of the panel's Gemma IFEval prompts
through the *panel's* harness config and compare `finish_reason` against these cells.

## Finding 6 — RESOLVED: the panel's empty *counts* are right; the *mechanism* is misattributed

Finding 5's discrepancy was tested directly. Gemma was re-run through the **panel's own path** —
lm-eval-harness, `--apply_chat_template`, MTP on, `max_gen_toks 4096`, `-c 16384`, port 8094 —
on IFEval `--limit 10`, which overlaps this leg's subset at doc_ids **0, 7, 9**.

| doc | harness path | direct path |
|---|---|---|
| 0 | **empty** | **empty** (`finish=length`) |
| 7 | **empty** | **empty** (`finish=length`) |
| 9 | **empty** | **empty** (`finish=length`) |

**3/3 empty on both paths. Explanation (2), "serving path", is ruled out.** The harness's overall
empty rate was **4/10 (40 %)** — consistent with the panel's reported 32.3 % over 541.

So the panel's empty counts reproduce. What does *not* survive is the attribution:

- The panel says Gemma had **zero budget-cap hits** and *"closes reasoning and EOSes without
  emitting an answer."*
- On the direct path those same docs show `finish_reason=length` with reasoning consuming the
  entire budget. **They are cap hits.**
- **lm-eval-harness records no `finish_reason` field at all** (sample keys: `arguments`, `doc`,
  `doc_hash`, `doc_id`, `filter`, `filtered_resps`, `metrics`, `prompt_hash`, `resps`, `target`,
  `target_hash`). The panel's instrument was structurally incapable of observing a cap hit.
  "Zero budget-cap hits" was not a measurement — it was an inference from an instrument that
  cannot see them, and the silent-closure story was built on top of it.

**Verdict:** Gemma fails the *same way Bonsai does* — over-thinking past the budget. There is no
silent-closure failure mode in 88 direct-path responses. The two-mechanism story in
`Battle16GB_Results.md` should become a one-mechanism story.

**This strengthens the article rather than weakening it.** Its own one-line take already says the
decisive variable *"is neither bits nor params: it's whether the model reliably exits the think
block with an answer."* That is now a **single unified mechanism across both arms**, verified at
the panel's own budget, with a demonstrated fix (`--reasoning-budget N>0`, 3/8 → 8/8 on both).
The headline scores are untouched throughout.

## Prediction scoring

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-RB1** | budget 0 LIVE on Gemma | 0.75 | **HELD** — 8/8 → 0/8 reasoning |
| **P-RB2** | budget 0 LIVE on Bonsai | 0.50 | **FALSIFIED** — byte-identical to −1 |
| **P-RB3** | Bonsai tokens drop ≥50 % at budget 0 | 0.70 | **FALSIFIED** — 2048 → 2048, 0.0 % |
| **P-RB4** | positive budget honoured as a bound | 0.65 | **HELD on both**, to ~1.3 % |
| P-RB5 | panel-level effect | 0.80 | **PREMISE FALSIFIED; prediction still unscored — see Finding 5** |

P-RB5 reasoned that a cap would leave Gemma unchanged *because her failure is silent closure, not
a cap*. On this instrument that premise is false: Gemma cap-dies 5/8 at 4096, never closes
silently in 88 responses, and a 1024 bound takes her 3/8 → 8/8. The panel-level prediction is
still not directly scored — that needs all 541 prompts with IFEval grading — but its stated
mechanism no longer stands, so it should not be carried forward as though it does.

Calibration note: after seeing `reasoning_mode: TAG_BASED` in Bonsai's boot log I said P-RB2's
0.50 "looks pessimistic in hindsight." That was wrong in the opposite direction — detecting the
thinking machinery is exactly what makes `N>0` work and says nothing about `0`.

## What this means for the article

**A re-run would change the results, and the flag is not one lever but two.**

- **Bonsai**: only `N>0` helps — and per Finding 3, **raising `max_gen_toks` is not an
  alternative**, because Bonsai expands its reasoning to fill whatever ceiling it is given
  (13992 chars at 4096 vs 8263 at 2048, still 5/8 cap-deaths). A bound converts cap-deaths into
  delivered answers at the panel's own budget (3/8 → 8/8), so Bonsai's IFEval would **rise** and
  the ternary win would **widen**. The published headline is understated, not threatened.
- **Gemma**: the follow-up the results doc named — *"rerun one Gemma leg with
  `enable_thinking:false`"* — **is reachable**, via `--reasoning-budget 0`. That arm can now be run.
- **⚠ The mechanism section needs rewriting before publication (Findings 5 + 6).** The headline
  table (73.0 vs 64.5, 94.0 vs 51.6) is untouched — those are scoring results and nothing here
  contradicts them, and the empty *rates* reproduce. What must change is the *explanation*:
  "Bonsai over-thinks, Gemma goes silent" is two mechanisms where there is one. Gemma's empties
  are cap-deaths too; the panel's harness simply could not see `finish_reason`. Rewritten, the
  article's own thesis gets stronger — one mechanism, both arms, one fix.

**Experimental-design consequence:** `--reasoning-budget 0` is *not* a matched treatment across
these two arms — it gives Gemma no-think and Bonsai nothing at all. Any re-run that sets `0` on
both and calls it controlled is uncontrolled. **`N>0` is the only setting that acts on both**, and
it is the one a matched re-run should use. It survives Gemma's MTP config (Finding 4), so the
panel's serving setup does not have to change.

**Untested and cheap: `--reasoning-budget-message`.** At budget 1024 Bonsai still shows 3/8
`finish=length` at `max_tokens 2048` while Gemma shows 0/8 — plausibly a difference in *how* each
exits a truncated think block. That flag injects a message before the forced `</think>` and would
control the handoff. It was never exercised here. If a re-run uses `N>0`, it is the next knob.

## Limits — one of which undercuts my own P-RB5

- **Gemma was only measured at `max_tokens` 2048, not the panel's 4096**, and this matters more
  than a normal budget caveat: the panel found Gemma had **zero** cap hits and failed by *silent
  closure*, whereas at 2048 she cap-dies 6/8. **The halved budget changed Gemma's failure mode**,
  so this leg cannot speak to the silent-closure mechanism at all. P-RB5 assumed a cap would not
  help Gemma because her failure isn't a cap; at *this* budget a cap helps her enormously
  (2/8 → 8/8). That is not evidence against P-RB5 — it is evidence that this instrument doesn't
  test it. **P-RB5's premise is now falsified outright (Findings 5 + 6):** Gemma was taken to
  4096 and to the panel's own harness, cap-dies either way, and never closes silently. The
  panel-level prediction remains unscored — that needs all 541 prompts with IFEval grading.
- **8 prompts, not 541**, chosen as the most-constrained. No IFEval scoring was performed; these
  are delivery counts, not accuracy.
- Bonsai's cap-death rates here do **not** restate the panel's 20.3 % empty rate — different
  prompt subset (the hardest 8) and, for the 2048 cells, a different budget. The numbers must not
  be presented side by side.
- K=1, temp 0, one rig, one build per model.
- Finding 1's mechanism is a hypothesis consistent with the boot logs, not a traced cause — the
  templates' kwargs were not read.
