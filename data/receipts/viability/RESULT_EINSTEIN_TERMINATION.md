# Result — einstein does not loop; the template's default effort does, on base weights and on DavidAU's tune

**Run 2026-09-12**, RX 9070 XT at 330 W. Pre-registered in `PREREG_EINSTEIN_TERMINATION.md` +
Amendments 1–3 (`93057c6`, `71ce474`, `e80b05a`, `44655ad`), every one committed before the data it
governs. Raw: `einstein_iq4/`, `einstein_iq2/`, unscored pilot in `einstein_pilot/`. Scored by
`tools/score_einstein.py`; output in `einstein_iq4/score_output.txt` and `einstein_iq2/score_output.txt`.

Prompted by donboyle on DavidAU's community page: *"The Einstein reasoning effort during coding agents
(at least in vscode) had no STOP. It would continue to improve endlessly."*

**Across both models, 72 generations: `xhigh` ran away 5 times in 24, `einstein` 0 in 24, capped
`einstein` 0 in 24.** Every runaway was inside `<think>` with an empty answer.

## Headline — primary, base Qwen3.8-27B UD-IQ4_XS, 36 generations

| arm | non-terminating | usable answer | median thinking |
|---|---|---|---|
| **A** `xhigh` — the template's default | **3/12** | 9/12 | 6,272 ch |
| **B** `einstein` | **0/12** | 12/12 | 4,166 ch |
| **C** `einstein` + 1,024-token cap | 0/12 | 12/12 | 3,502 ch |

**Einstein never ran away. The default effort did** — and every one of its runaways is the same cell:

| arm A `xhigh` | rep 1 | rep 2 | rep 3 |
|---|---|---|---|
| `E-C1` duration parser | **RUNAWAY** 8,192 tok, 4 drafts | **RUNAWAY** 8,192 tok, 5 drafts | **RUNAWAY** 8,192 tok, **13 drafts** |
| `E-C2` dedupe CLI | stop, 3,401 tok | stop, 2,797 tok | stop, 5,136 tok |
| `E-I1`, `E-I2` ideation | stop, 138–714 tok | | |

On `E-C1`, xhigh hit the 8,192-token ceiling **on all three seeds with an empty answer**, rewriting
`def parse_duration(...)` inside `<think>` four, five and thirteen times. Einstein, on the same seeds,
finished all three. **That is donboyle's symptom — "it would continue to improve endlessly" —
reproduced, but under `xhigh`, not `einstein`.** It is item-specific and seed-independent: a property
of this task under this instruction, not a sampling accident. (Descriptive; n = 3 per cell.)

### What the loop is doing

The 13-draft generation (rep 3, 27,343 chars of thinking) is not cycling through identical versions.
It keeps **re-opening a decision it has already made — the function's return-type annotation:**

| draft | at char | what the model is weighing just before it |
|---|---|---|
| #4 | 10,360 | "`float` requires Python 3.10. Could avoid for compatibility" |
| #5–#7 | 15,350–15,466 | "For broad compatibility, no union … `-> "int \| float"` no. Simpler:" — **three drafts in 116 characters** |
| #10–#11 | 25,674–25,797 | "`int \| float` fails [on 3.9]. To maximize compatibility … Or no return annotation. Simpler:" |
| #12–#13 | 26,440–26,809 | where the constants live — "inside function to be self-contained" |

The same compatibility question returns about 10,000 characters after it was apparently settled, and
the generation hits the ceiling part-way through yet another edge case (negative durations).

**The text `xhigh` injects is *"validate key assumptions, consider plausible alternatives"* — and a small
coding task has an unbounded supply of trivially plausible alternatives** (annotation style, where
constants live, what to do with a negative input). Nothing in the instruction says when an alternative
stops being worth considering. It is the missing-terminator shape `RESULT_SEARCH_ASYMMETRY.md`
describes, produced by the template's *default* effort. *(Interpretive: one generation read closely;
the other two are not characterised here.)*

## Predictions

| id | prediction | result |
|---|---|---|
| P-E1 | einstein median thinking > xhigh | **FALSIFIED** — 4,166 vs 6,272 ch |
| P-E2 | einstein reaches ≥5,000 reasoning tokens in fewer than half of generations | **CONFIRMED** — **0/12**. The largest einstein generation was 4,687 tokens *in total*. The mode's own "at least 5000 tokens" floor is never met |
| P-E3 | einstein non-termination > xhigh | **FALSIFIED** — 0/12 vs 3/12 (Fisher p = 0.217: the reverse direction, underpowered) |
| P-E4 | the cap drives non-termination to 0 | **CONFIRMED, vacuously** — B never ran away, so the cap had nothing to fix |
| P-E5 | capped einstein still gives a usable answer ≥80% | **CONFIRMED** — 12/12 |
| P-E6 | the runaway is inside `<think>`, not post-answer | **CONFIRMED** — 3/3 runaways have an empty answer |
| P-E7 | einstein's overrun is larger on ideation than coding | **CONFIRMED** — B/A thinking ratio 4.08× ideation vs 0.23× coding. Little independent weight: the pilot already pointed this way, as Amendment 3 stated in advance |

**Sensitivity — excluding the 4 pilot-previewed cells:** A 2/10 non-terminating, B 0/10, C 0/12.
Every verdict above is unchanged.

## Two things measured that were not predicted

**Cross-process determinism.** All 4 pilot-previewed cells reproduced **byte-for-byte** on a
freshly restarted server with a different prompt-cache history — pilot and scored run agree to the
token (8,192 / 3,084 / 138 / 1,159). At `-np 1`, fixed seed, q8_0 KV, this build is deterministic
across processes, not merely within one. **It is not evidence that prefix-cache reuse is harmless:**
`hermesagent20/DETERMINISM_ROOT_CAUSE.md` measured reuse changing bytes on the P100s, and the
requests here shared only short prefixes (the injected system texts diverge within a few tokens), so
little was ever reused.

**The cap does not relocate the work.** Where the cap bound (6 of 12 B/C cells) it cut einstein's
thinking on `E-C1` by 2–4× with **no outcome change and no longer answer**: the median C/B answer-length
ratio is **1.00×**. One cell (`E-C1` rep 1) wrote a 2.4× longer answer under the cap; I flagged it
mid-run as a possible pattern. Across all six it is not one.

## What this means for donboyle's fix

- **In single-turn use, the einstein text is not what loops** — on base weights at IQ4_XS and on
  DavidAU's own IQ2_M tune alike. It produces *less* thinking than the default and terminated 24 of
  24 times. The persona barely engages at all (a crude marker count
  finds one "brainstorm" across the pilot's einstein generations and no agents, `IdeaArray`, or
  Sternberg).
- **The loop we did reproduce is inside `<think>`** — the right lever for it is a thinking budget
  (`reasoning_budget_tokens`), not a paragraph of stop-text appended to the prompt. Our own
  overthink receipts measured that distinction directly: the cap removed every runaway at no cost on
  answerable questions, and injected stop-text changed 0 of 24 outcomes
  (`RESULT_OVERTHINK_INJECTION_Q6K.md`).
- **His screenshots show something this test cannot.** He describes the model producing an improved
  deliverable *each time*, repeatedly — visible, complete outputs. That is a **post-answer** loop, which
  in a VS Code agent is most likely the harness re-prompting after each answer. Single-turn generation
  cannot reproduce that, and P-E6's confirmation here says nothing about it. **The question that
  decides his fix:** does the model finish an answer and then start again, or does it stay in one
  thinking block? If the former, the fix belongs in the agent's stop condition, not the template.

## The inert sampler text

`[Temperature: 1.25]` and `[TopP: .2]` sit inside the einstein system text. They are characters the
model reads, not sampler settings; einstein mode cannot set temperature. Anyone who believes they are
running einstein at 1.25 is running it at their client's default. Not tested — true by inspection.

## Secondary — DavidAU `…735-882…-MTP-IQ2_M`, his template, 36 generations

| arm | non-terminating | usable answer | median thinking |
|---|---|---|---|
| **A** `xhigh` | **2/12** | 10/12 | 5,873 ch |
| **B** `einstein` | **0/12** | 12/12 | 1,922 ch |
| **C** `einstein` + cap | 0/12 | 12/12 | 1,922 ch |

**The same direction on DavidAU's own weights.** Einstein never ran away; xhigh did twice — `E-C1`
and `E-I1`, both on rep 3 (seed 2003), both 8,192 tokens with an empty answer (P-E6: 2/2 inside
`<think>`). **Every prediction scores exactly as it did on the primary:** P-E1 and P-E3 falsified
(0/12 vs 2/12, Fisher p = 0.478); P-E2, P-E4 (vacuously), P-E5, P-E6 and P-E7 confirmed. On the tune,
einstein thinks *even less* relative to xhigh (1,922 vs 5,873 ch median) than on base weights. The
cap bound in only 2 of 12 B/C cells and changed 0 outcomes. Output: `einstein_iq2/score_output.txt`.

**The runaway is not item-bound on the tune.** On base IQ4_XS it was `E-C1` on every seed; on the
IQ2_M tune it is two different items on one seed. Four items and three seeds are too few to say more
than that the failure belongs to `xhigh` in both models, and to `einstein` in neither.

**Cross-process determinism, again:** the IQ2_M pilot's 4 previewed cells reproduced byte-for-byte
(1,949 / 1,452 / 374 / 444 tokens).

**Deviation — the last 5 secondary cells ran on a second server process.** The harness killed the
chain on "low memory" at ~14:24, and with it the llama-server the chain had launched, mid-generation in
`A/3/E-I1`; the runner writes only complete rows, so none was left partial. The committed
`einstein_chain.sh` was re-run unchanged: it skipped every recorded cell and ran `A/3/E-I1`,
`A/3/E-I2`, `B/3/E-I1`, `B/3/E-I2` and `C/3/E-I2` on a fresh IQ2_M server. Given the cross-process
reproducibility shown on both models this is not expected to matter, but it is declared — and
`A/3/E-I1`, the cell in flight at the kill, is one of the two runaways.

## What is not claimed

- **Nothing about agentic, multi-turn use**, which is where donboyle saw the problem.
- **No capped-xhigh arm.** The cap's value against xhigh's runaway is inferred from the overthink
  receipts, not measured here.
- **n = 3 per cell, 4 items.** The `E-C1` finding is a clean pattern at small n, not a rate.
- **The tune is tested only at IQ2_M**, and the primary uses base weights (Amendment 1).
- Spoon mode was not tested.
