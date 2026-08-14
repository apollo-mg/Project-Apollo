# Qwen 3.8 27B low-bit 2x2: all four cells 8/8. The instrument saturated.

**Date:** 2026-08-14, launch day. Predictions sealed in `PREREG.md` before any run.
**Hardware:** RX 9070 XT 16 GB, both models fully resident (`-ngl 999`), f16 KV, `-fa on`,
**no** TurboQuant KV, **no** MTP draft, `-c 8192`. Quant is the only variable.
**Sampling:** `temperature 0`, `top_k 1`, `seed 1234`, `n_predict 512`. K=1.

## Result

| cell | graded correct | stop reasons | loops | total tokens |
|---|---|---|---|---|
| `UD-IQ2_M` thinking on | 8/8 | `{stop: 8}` | 0 | 1208 |
| `UD-IQ2_M` thinking off | 8/8 | `{stop: 8}` | 0 | 780 |
| `UD-IQ3_XXS` thinking on | 8/8 | `{stop: 8}` | 0 | 854 |
| `UD-IQ3_XXS` thinking off | 8/8 | `{stop: 8}` | 0 | 666 |

Every gradeable item correct in every cell: Canberra, 252, 2:29, all eight planets in
order, a working `is_palindrome`, "exactly three colors one per line" honoured (3 lines in
all four), 1/0 undefined, longform under the sentence cap. Zero cap-deaths, zero
truncations, zero repetition loops anywhere.

## Sealed predictions, scored

| # | prediction | conf | outcome |
|---|---|---|---|
| P1 | thinking gap larger at IQ2 than IQ3 | 0.70 | **unresolvable** — both gaps are 0 pp |
| P2 | IQ2 gap smaller than Puzzle's 25.0 pp | 0.60 | **confirmed** (0 pp vs 25.0) |
| P3 | thinking-off produces >=1 loop or non-stop failure | 0.55 | **FALSIFIED** — 0 of 16 |
| P4 | failures are stopping-rule, not wrong-answer | 0.65 | **vacuous** — no failures |
| P5 | IQ3 thinking-on within 5 pp of IQ2 thinking-on | 0.50 | **confirmed** (0 pp apart) |

## The honest headline: this test could not have measured what it set out to measure

The hypothesis under test — from `battle16gb/PUZZLE_LADDER_FA_ON.md`, where the thinking
gap collapsed 25.0 pp at Q2 to 3.3 pp at IQ4 — requires cells that *can* differ. Eight
hand-checkable prompts against a strong 27B produces 100% in all four cells, so no gap of
any size could appear. Puzzle used HumanEval+, 164 problems, K=3: **492 samples per cell
against 8 here.**

This is a **null from insufficient resolution**, not evidence against the substitution
finding. Reporting it as "the Puzzle result doesn't replicate" would be wrong.

## What does survive

**1. `UD-IQ2_M` is not brittle, and that was not the expectation.** Going in, this fleet's
own history predicted "2-Bit Drunk" schema loops, cap-deaths, and the stopping-rule failure
that `battle16gb` Finding 5 documents. On a dense 27B whose IQ2 quant carries **96 `IQ1_M`
tensors** — a full tier below its label — none appeared. P3 was falsified cleanly.

**2. A consistent token-cost gradient at identical accuracy.** IQ2 spends **41% more
tokens** than IQ3 to reach the same 8/8 (1208 vs 854, thinking on), and the ordering holds
in 7 of 8 prompts:

| prompt | IQ2 on | IQ3 on | IQ2 off | IQ3 off |
|---|---|---|---|---|
| factual | 34 | 29 | 3 | 3 |
| arith | 92 | 81 | 172 | 162 |
| format | 244 | **139** | 6 | 6 |
| reason | 126 | 106 | 414 | 324 |
| code | 295 | **165** | 39 | 44 |
| loopbait | 89 | 98 | 48 | 48 |
| refuse | 67 | 55 | 2 | 2 |
| longform | 261 | 181 | 96 | 77 |

The two largest gaps are `format` (244 vs 139) and `code` (295 vs 165) — both cases where
the model must *stop* at the right place. IQ2 gets there, but spends more getting there.

**This is a hypothesis, not a finding.** K=1, and token counts at temp 0 on this fleet are
not established as reproducible. But it is the shape a real degradation signal would take
before accuracy moves, and it is directly measurable: if quantisation damage shows up as
verbosity before it shows up as wrongness, token count is a **more sensitive instrument
than pass rate** at these quant levels. Worth a proper test.

**3. Thinking-off costs more tokens than thinking-on on multi-step items** — arith 172 vs
92, reason 414 vs 126 at IQ2, same direction at IQ3. With thinking disabled the model
reasons in the visible channel instead of a think block and still lands correct. The
channel moves, the answer does not.

## Correction and an unexpected result: `reasoning_effort` is inverted

Prompted by @JabbaTheDuck reporting thought loops on Qwen 3.8 27B, fixed with
`chat-template-kwargs = {"reasoning_effort": "low"}` — a different knob than the one used
above. Two things came out of checking it.

**Harness defect (does not change the result).** `llama-server` returns reasoning in a
**separate `reasoning_content` field**, not inline in `content`. The runner captured only
`content`, so every `<think>` block was silently dropped and the raw JSON shows zero think
blocks in all 32 responses. That looked at first like the thinking arm never engaged.

Verified directly against the live server, same prompt, `temperature 0`:

| kwargs | `reasoning_content` | completion tokens | answer |
|---|---|---|---|
| `{"enable_thinking": true}` | **264 chars** | 106 | 2:29 |
| `{}` (default) | 264 chars | 106 | 2:29 |
| `{"enable_thinking": false}` | **0 chars, absent** | 324 | 2:29 |

So the arms were valid — `enable_thinking: false` genuinely suppresses reasoning, `true`
produces it, and the 2x2 above measured what it claimed to. The token totals it reports are
`completion_tokens`, which the server counts across both fields, so those are also correct.
The runner has been patched to record `reasoning_content` length per response.

**Corrected: `reasoning_effort` is not simply inverted. It is prompt-dependent.**

An earlier version of this section claimed `low` costs 2.6x more than `high` and that the
control "does not behave as a throttle". **That generalised from a single prompt and is
withdrawn.** Testing the documented ladder across three prompts, same seed, `UD-IQ3_XXS`:

| prompt | `xhigh` | `medium` | `low` | ordering |
|---|---|---|---|---|
| reason (train times) | 106 t / 264 c | 253 t / 396 c | **277 t / 523 c** | inverted, monotonic |
| code (palindrome) | 165 t / 536 c | **227 t / 744 c** | 109 t / 315 c | **non-monotonic** — medium highest |
| format (three colors) | 139 t / 527 c | 131 t / 499 c | 122 t / 468 c | as named, but a 12% spread |

*(t = completion tokens, c = `reasoning_content` chars.)*

There is no consistent direction. The 2.6x inversion is real **on the reason prompt** and
does not survive to the other two. On `code`, `low` is the *cheapest*; on `format` the
ordering matches the naming but the total spread is 17 tokens.

What does hold across every test:

**`xhigh`, `high`, and the default are byte-identical** — 264 chars / 106 tokens on the
reason prompt, character-for-character. The Qwen docs list `xhigh` as the default, so
`high` and `xhigh` evidently resolve to the same template output. This is not a silent
fallback: an invalid value (`"banana"`) returns **HTTP 500**, so the template validates its
input and `high` is genuinely accepted.

**So the usable settings are three, not four:** default/`xhigh`/`high` (one behaviour),
`medium`, and `low`.

On @JabbaTheDuck's loop fix — `low` did change behaviour on the one prompt where the
difference was large, shifting reasoning into a longer, fully-worked visible answer rather
than a terse internal trace. That remains a plausible mechanism for why it stopped a loop,
and it remains untested: no configuration produced a loop on this fleet, and the effect
size varies by prompt, so it should not be presented as a general tuning rule.

**Method note for anyone repeating this:** a single prompt was enough to produce a clean,
confident, monotonic result pointing the wrong way. Three prompts were enough to destroy
it. K=1 on one prompt is not a measurement of a sampling parameter.

## Limits

- **K=1.** `agent-benchmark-determinism` records temp-0 on this fleet as non-reproducible
  (HA-04 was bistable 35/100/100/35). Existence proof, not a rate.
- **Ceiling effect**, stated above. Discriminating power at this difficulty is ~zero.
- **One ordering.** Thinking-on ran first in all cells; not reversed.
- **Two quants is a two-point line** and cannot distinguish gradual decay from a cliff.
- Both files are unsloth *dynamic* recipes with different tensor mixes, so this compares
  two files, not two clean bit-depths.

## Next, if this is pursued

The prompt set is the limiting instrument. Escalating means HumanEval+ at K>=3 — the same
apparatus `data/receipts/humaneval-plus/` already contains — or an agentic/tool-calling
task, which is where quantised models on this fleet have historically actually broken
(`loop-detector`, `hermesagent20`, the "2-Bit Drunk" schema loops). A trivia set was never
going to find the edge on a model this strong.
