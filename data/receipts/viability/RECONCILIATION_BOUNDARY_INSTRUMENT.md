# Reconciliation — six documents, one instrument

**2026-09-21. Map and corrections, not a new design.** Written after `ledger_precheck.py`
surfaced, on the morning `.194` came up for a pilot, that `CORPUS_DESIGN_v2.md` (09-20) had been
authored without knowledge of `A1_MEASUREMENT_CORPUS_SPEC.md` (08-20) — which had already done the
power analysis and landed an order of magnitude away on sizing.

**Nothing here supersedes those documents. This says how they fit and what each owes the others.**

## They are all measuring one capability

| document | date | angle on it |
|---|---|---|
| `CALIBRATION_TIER_DESIGN.md` | 08-20 | the 16-item gate: does it abstain on an unanswerable question |
| `A1_MEASUREMENT_CORPUS_SPEC.md` | 08-20 | the same, sized to carry a **comparison** rather than a gate |
| `BOUNDARY_TEST_DESIGN.md` | 08-22 | can it finish **at all**, at what cost — deliberately anecdotal |
| `NOTE_OVERTHINK_DETECTOR.md` | 09-11 | does thinking **length** reveal it has gone past the boundary |
| `PREREG_OVERTHINK_INJECTION.md` | 09-11 | can a nudge pull it back once it has |
| `CORPUS_DESIGN_v2.md` | 09-20 | does it **ask instead of acting** when the request is underdetermined |

The unifying question is **"does the model recognise it lacks what it needs, and stop?"** The first
five approach it as a *knowledge* boundary (the answer does not exist). v2 approaches it as a
*specification* boundary (the instruction does not determine an action). Those are two faces of one
capability, and `CALIBRATION_TIER_DESIGN` already names why it is the interesting one here:

> AA scores Qwen3.8-27B at **70 % non-hallucination** against **23 % raw knowledge accuracy**.
> For a 27B that trades blows with models a hundred times its size, **knowing the boundary *is* the
> product**. ... Every instrument this project owns is blind to that capability.

## What v2 owes A1 — three corrections

**1. Sizing. v2 is roughly an order of magnitude short, and by the wrong unit.**

A1's argument: McNemar power comes only from **discordant pairs**; items both arms get right or
both get wrong contribute nothing. Working target **240 per arm**, sized at the pessimistic end,
and the analysis must **report achieved discordance** rather than assume power — *"a run that
yields 12 discordant pairs is underpowered no matter how many items it contained; that is precisely
how HumanEval+ died."*

v2 proposed 45 items and, worse, made the unit of comparison a **threshold per family** — six
ordinal measurements per arm. Rung design cannot rescue six measurements.

**But the designs compose rather than conflict.** Graded rungs are a *mechanism for manufacturing
discordant pairs*: rungs near the act/ask boundary are exactly where two arms disagree, which is
where all the power lives. A1 says how many are needed; v2 says how to generate them efficiently.
**Keep the rungs, size by A1, report achieved discordance.**

**2. Construction. v2's ambiguity is asserted; A1 shows how to make it decidable.**

A1 on its own predecessor's largest liability: sixteen items whose unanswerability is *"asserted
from memory ... that does not scale to 480, and hand-verification of 480 invented entities is not a
real plan."* Its fix is closed sets — answerable = a question about a **member**, unanswerable =
the identical template about a **non-member**, so unanswerability becomes a **set-membership
decision** and the arms are matched by construction.

**This transfers directly, and v2's own fixture already does it once by accident.** "Email Dave" is
ambiguous **iff** `|{contacts matching /Dave/}| > 1` — and the seed has two Daves. That is not an
authorial claim, it is a cardinality fact computable from `seed.json`. Generalised: **underspecification
becomes a function of world state, not of the author's judgement.** Referent ambiguity is set
cardinality; unsatisfiability is set emptiness; scope ambiguity is an unbounded selector. Items can
then be *generated* against a fixture and re-verified whenever the fixture changes, which is what
makes 240 per arm a real plan instead of an authoring marathon.

**3. Hardware and ordering. Both of yesterday's operational assumptions are wrong.**

A1, from measurement on 08-21 rather than estimate:

- The unanswerable arm costs **4-9x** its partner (median 5,090 vs 724 chars). At 240 pairs:
  **~521k tokens, ~18.8 h per sweep, ~37.6 h for a two-quant comparison** on 2x P100.
- **"A1 does not belong on Pascal."** The 9070 XT runs this model class several times faster and
  needs no turbo KV. Yesterday's plan put the pilot on `.194`. *(A1 says to measure decode on the
  9070 before committing — that measurement is still owed.)*
- **"Effort is now a cost variable as well as a confound ... the effort sweep is a prerequisite for
  sizing, not a follow-up."** v2 has effort as a crossed factor, which is right, but scheduled it
  *after* the pilot. It has to come first, because `xhigh` vs `medium` changes the token bill that
  the sizing is computed from.

## What A1 owes v2, and what the others contribute

- **v2 -> A1: difficulty calibration.** A1 sizes for discordance but has no mechanism to *produce*
  it; graded rungs are that mechanism. A1's own gate died of the opposite problem v1 died of, and
  neither document had the other's fix.
- **`NOTE_OVERTHINK_DETECTOR` -> both: the corpus it needs may be this one.** It reports 572 median
  chars for answerable-correct vs 4,196 for confabulation, a >=1,000-char threshold catching 82 % of
  failures at 0 % false positives — then states the falsifying corpus is **missing**, because *"our
  answerable arm is easy (24/24 correct, max 845 chars)"*. A graded ladder supplies exactly the hard
  answerable items that would produce the false positives. **And the driver already logs
  `think_chars` as of 09-20**, added for token-cap sizing without knowing this hypothesis existed.
- **`PREREG_OVERTHINK_INJECTION` -> blocked, and now formally requested.** Its treatment arm cannot
  run through the current API; `NOTE_MIDTHOUGHT_INJECTION_FEASIBILITY` established why and the
  `reasoning_budget_action: "continue"` request went to buun 09-21.
- **`BOUNDARY_TEST_DESIGN` -> the escape hatch.** Stays a separate, anecdotal class, invoked when an
  item fails to terminate. Not folded in; conflating it with daily-use quality is how `NO-STOP` got
  over-claimed once already.

## What is actually next

1. **Measure decode for this model class on the 9070 XT.** A1 owes this and it decides the host.
2. **Effort sweep before sizing** — `medium` vs `xhigh` token bill on a handful of items.
3. **Re-derive the item count from A1's table** using observed discordance, not a guess.
4. **Rebuild v2's families as fixture-computed rather than hand-asserted**, so they can be generated
   and re-verified at 240/arm.
5. Only then: pilot.

**Not started.** `.194` is up and idle; nothing here says to use it, and A1 says not to.
