# PREREG — which clause of the `xhigh` instruction causes the confabulation?

**Written 2026-09-07, before the run.**

## Setup

`RESULT_EFFORT_IS_A_PROMPT_EDIT.md` established that `reasoning_effort` is injected system
text, not a compute setting. Rendered against this server's own template:

- `xhigh` / unset → **207-char** system block (the receipt's "237" counted the block with its
  markers; the text itself is 207)
- `medium` → **0 chars**
- `low` → 136 chars

> *"Reasoning effort is set to xhigh. Please think carefully through the task, **validate key
> assumptions**, **consider plausible alternatives**, and prioritize correctness, consistency,
> and clarity in the final answer."*

`RESULT_A6_LOW_RUNG.md` measured what that string costs on the calibration arm: abstention
13/24 at `xhigh` against 21/24 at `medium` and `low`, plus all 5 NO-STOP. Since `medium`
injects nothing, **the string is the entire difference between those arms.** What is not known
is which clause does it.

Two clauses should pull opposite ways on a false-premise item:

- *"validate key assumptions"* — nearly a direct instruction to check the premise. Should help.
- *"consider plausible alternatives"* — on a question about a thing that does not exist, close
  to an instruction to generate candidate answers. Should hurt.

## Design

Four arms, all at `--effort medium` (0-char system block), card sampling, seeds 1001–1003,
`.194`/Q6_K, same binary and flags as `RESULT_A6_LOW_RUNG.md`.

| arm | injected text | chars |
|---|---|---:|
| A control | none — reuse the existing `card_medium_rep*` data | 0 |
| B full | the entire `xhigh` string | 207 |
| C validate | `Reasoning effort is set to xhigh. Please validate key assumptions.` | 66 |
| D alternatives | `Reasoning effort is set to xhigh. Please consider plausible alternatives.` | 73 |

The frame sentence is held constant across B/C/D so only the clause varies.

**The known confound, and why B exists.** `run_fixture.py` sends no system role — the effort
text normally arrives via the chat template into the *system* block, whereas these arms
prepend to the **user** turn. Position is not controlled. **B is the positive control:** if
the full string in the user turn reproduces `xhigh`'s ~13/24, position does not matter here
and C/D are interpretable. If B looks like `medium` instead, position dominates, the
decomposition is void, and that is the result.

`run_fixture.py` is not modified — the text is carried in `tier_cal.prompt` of three generated
fixture copies (`fixture_clause_*.json`), so the instrument is byte-identical to the arms
being compared against.

## Predictions

| # | prediction | confidence |
|---|---|---:|
| Q1 | **B reproduces xhigh** — abstention ≤ 16/24, i.e. clearly worse than medium's 21 | 0.55 |
| Q2 | **D (alternatives) is worse than C (validate)** on abstention | 0.70 |
| Q3 | C is no better than the A control (21/24) — "validate key assumptions" does not *help*, it just fails to hurt | 0.60 |
| Q4 | `CAL-U3` answers `1906` in all 9 runs across B/C/D, as it did in all 9 across the effort ladder | 0.85 |
| Q5 | No arm produces NO-STOP — the 5 NO-STOP at real `xhigh` need the system-block position, not just the text | 0.40 |

Q1 and Q5 are deliberately in tension: Q1 says the text alone reproduces the abstention loss,
Q5 says it does not reproduce the non-termination. If both hold, **the string costs calibration
from either position but only runs away from the system block** — which would mean two
different mechanisms are bundled in one setting.

## Stopping rule

3 reps × 3 arms, then score. No peeking-and-extending.

## Limits acknowledged up front

8 items, 3 reps, one node, one quant. Direction-finding on a gate-sized fixture, not a
measurement. A null between C and D would be uninformative at this n rather than evidence of
no effect.

---

## Amendment 1 — interim peek at arm B rep 1 (written 2026-09-07 ~14:15, BEFORE looking)

**This is a deviation from the stopping rule above and is recorded as one.** The original rule
said 3 reps × 3 arms then score, no peeking. Arm B is running ~3.6 min/item against the ~1.5
min/item this was costed at, so arm B alone is ~3 h and the full design is plausibly 6–9 h of
`.194`. The peek is authorised to decide **whether to stop**, never whether to extend.

Why that asymmetry matters: a peek that can only trigger an abort cannot manufacture a
positive finding. A peek that can trigger an extension can. This one is gated to abort only.

**Decision rule, fixed before the data is seen.** Rep 1 has 8 unanswerable items. Reference
rates from `RESULT_A6_LOW_RUNG.md`, expressed per rep: `xhigh` ≈ 4.3/8 abstained,
`medium`/`low` = 7/8.

| B rep-1 abstained | reading | action |
|---|---|---|
| **0–3 / 8** | decisively `xhigh`-like — the string reproduces from the user turn | **continue**; C and D are interpretable |
| **8 / 8** | decisively `medium`-like — position dominates, decomposition void | **abort** C and D; that null is the result |
| **4–7 / 8** | ambiguous at this n | **let it ride** to full 3 reps |

The ambiguous band is deliberately wide. One rep of 8 binary items has poor power — a 3-item
gap between the `xhigh` and `medium` expectations is well inside binomial noise at n=8 — so
most outcomes should land in "keep running". Operator preference, stated before the peek:
**let it ride when uncertain.**

If the rule says continue, no further peeking; the next look is at 3 complete reps.
