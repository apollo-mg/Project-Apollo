# Result — `--reasoning-budget 0` is inert; `N>0` rescues every empty (Bonsai leg)

**Status: PARTIAL.** Bonsai 3/3 cells complete. **Gemma 0/3 — not run.** Pre-registered in
`PREREG_REASONING_BUDGET_SMOKE.md`, logged before any inference.

**Date:** 2026-08-08. RX 9070 XT 16GB (gfx1201), stock clocks, `engines/llama_cpp_bonsai/build_hip`.
Ternary-Bonsai-27B Q2_g64 (7.59 GB), `-c 32768 -ngl 99 -fa on` fp16 KV, `--jinja
--reasoning-format deepseek`, temp 0 / top_k 1, `max_tokens 2048`, 8 most-constrained IFEval
prompts from the panel's 541.

## Headline

| budget | w/reasoning | **w/answer** | mean reason chars | mean tokens | finish=stop |
|---|---|---|---|---|---|
| **−1** (unrestricted) | 8/8 | **0/8** | 8263 | 2048 | 0/8 |
| **0** (immediate end) | 8/8 | **0/8** | 8263 | 2048 | 0/8 |
| **1024** (bounded) | 8/8 | **8/8** | 4150 | 1617 | 5/8 |

```
answers delivered:   -1 = 0/8      0 = 0/8      1024 = 8/8
```

**Two findings, opposite directions.**

### 1. `--reasoning-budget 0` is INERT on this model

Budget 0 output is **byte-identical** to unrestricted: all 11 recorded fields match on all 8
responses, and the generated reasoning text matches 8/8. Not "similar" — identical. The flag
does nothing.

This is not a determinism artifact being mistaken for inertness; temp 0 explains why *repeats*
match, not why a flag that should have suppressed thinking entirely left 8263 chars of it intact.

**Mechanism (hypothesis, not proven):** `0` means "immediate end", which needs the chat template
to expose a no-think path (`enable_thinking: false`). Bonsai ships a ChatML-style template with
`reasoning_mode: TAG_BASED` (`<think>`/`</think>`, recorded in `cells/BONSAI_bm1_serving.txt`)
and apparently no such kwarg, so the request silently no-ops. `N>0` needs no template support —
the server counts thinking tokens and injects `reasoning_end` itself. That asymmetry would
explain why one works and the other does nothing. Testing it requires reading the template's
kwargs, which this leg did not do.

### 2. `--reasoning-budget 1024` converts every cap-death into an answer

**0/8 → 8/8.** Reasoning halves (8263 → 4150 chars), total tokens drop 21 %, and 5/8 responses
now terminate on `stop` rather than dying at the cap. Estimated reasoning tokens at the bound:
**~1037** (chars ÷ 4) against a 1024 budget — near-exact, consistent with precise enforcement.
That estimate is an estimate: the server does not return reasoning tokens separately.

## Prediction scoring

| id | prediction | conf | outcome |
|---|---|---|---|
| **P-RB2** | budget 0 LIVE on Bonsai | 0.50 | **FALSIFIED** — byte-identical to −1 |
| **P-RB3** | completion_tokens drop ≥50 % at budget 0 | 0.70 | **FALSIFIED** — 2048 → 2048, 0.0 % |
| **P-RB4** | positive budget honoured as a bound | 0.65 | **HELD** on Bonsai, emphatically |
| P-RB1 | budget 0 LIVE on Gemma | 0.75 | **UNSCORED** — cell not run |
| P-RB5 | panel-level effect | 0.80 | **UNSCORED** by design; needs the full 541 @ 4096 |

Two falsifications, both on the 0-budget arm. Note the direction of my error: after seeing
`reasoning_mode: TAG_BASED` in the boot log I said P-RB2's 0.50 "looks pessimistic in hindsight."
It was not pessimistic enough — the wiring being present is what makes `N>0` work and says
nothing about `0`. Detecting the machinery is not the same as the flag exercising it.

## What this means for the article

**The answer to "would a re-run get different results" is yes — and in Bonsai's favour.** A
bounded budget converts cap-deaths into delivered answers, so Bonsai's IFEval would rise and the
ternary win would widen. The published headline is not at risk from this flag; it is understated.

**But the flag that does it is `N>0`, not `0`** — and the results doc's named follow-up
("rerun one Gemma leg with `enable_thinking:false`") may not be reachable through
`--reasoning-budget 0` at all if the same inertness holds on Gemma. `-rea/--reasoning off` is a
separate flag and the more likely route; untested here.

## Limits

- **8 prompts, not 541.** The most-constrained subset, chosen because deliberation is longest
  there. Not a panel and not an accuracy measurement — no IFEval scoring was performed.
- **`max_tokens` 2048, not the panel's 4096.** The 8/8 cap-death rate at −1 is therefore a
  *tighter-budget* result and does **not** reproduce or restate the panel's 20.3 % empty rate.
  The two numbers must not be presented side by side without this.
- **Gemma entirely unmeasured.** Every Gemma prediction is unscored.
- **One model, one build, one rig.** K=1, temp 0.
- The mechanism in §1 is a hypothesis consistent with the evidence, not a traced cause.
