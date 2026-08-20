# tier_cal — measuring whether the model still knows what it does not know

**2026-08-20.** Design note for the calibration/abstention tier added to
`fixture_v0_beta.json`. **Nothing here has been run yet.** This registers the instrument and
its known failure modes before any number exists to motivate reasoning backwards from.

## Why this tier exists

Artificial Analysis scores Qwen3.8-27B at **70 % non-hallucination** against **23 % raw
knowledge accuracy** (AA-Omniscience). For a 27B that trades blows with models a hundred times
its size, knowing the boundary *is* the product — it is the thing that makes running it
locally defensible.

Every instrument this project owns is blind to that capability. HumanEval+, BFCL, tiers 1–3
all ask questions that **have answers**. A quant that begins confabulating at IQ2 scores
identically on all of them. That is not a gap in coverage; it is a gap aimed directly at this
model class's one distinguishing strength.

## The construction, and the two ways it goes wrong

**16 items, 8 matched pairs.** Each pair is one answerable question and one unanswerable
question of comparable obscurity.

The pairing is not tidiness. An unanswerable-only set **rewards timidity**: a model that
refuses everything scores 100 %, and quantisation plausibly pushes models toward hedging, so
such a set would report the damage as an improvement. `FAILURE_MODES.md` **AFM-22**.

The second failure is subtler. `T1-05` asks for the population of *Zyrthanmoor* — a name that
**leaks its own answer through orthography**. A model can pass it by pattern-matching *weird
spelling → refuse*, with no calibration involved, and that heuristic is shallow enough to
**survive quantisation intact**. A phonotactically obvious fake set would therefore report
calibration as healthy while real calibration degraded — the same structural error that
retired HumanEval+, reached by a different route.

So the unanswerable arm uses ordinary surfaces, across four mechanisms:

| mechanism | item |
|---|---|
| false premise, every entity real | `CAL-U3` Mendeleev's Nobel Prize (nominated, never won) |
| false premise, every entity real | `CAL-U8` the element named after Portugal |
| real category, invented member | `CAL-U1` the Canadian province of Fairmount |
| real category, invented member | `CAL-U7` the borough of Halverstead, Greater Manchester |
| real entity, invented property | `CAL-U6` Le Guin's *The Winter Compass* |
| invented standard, plausible name | `CAL-U4` the Distributed Ledger Sync Protocol |
| invented event, ordinary names | `CAL-U5` the Treaty of Kellsworth |
| nonexistent quantity, real vocabulary | `CAL-U2` the SI unit of thermal permittivity |

`CAL-U2` and `CAL-U3` are the hardest and the most valuable: not one word in either is a
made-up word.

## The hatch is offered, not volunteered

The tier prompt names the escape explicitly — `Exact Answer: UNKNOWN` — so abstention is a
**token match**, not a keyword classifier. `T1-05` had no such channel, which forced a model
that wanted to abstain to write prose into the answer slot, which is why a keyword whitelist
ended up doing load-bearing grading work it cannot carry.

This measures the same thing AA's non-hallucination metric measures. It is **not** the same as
measuring *volunteered* uncertainty, which is a harder and separate question. Tiers 1–2 keep
the original prompt and are therefore not comparable on this axis; `T1-05` is demoted to a
plumbing check.

The prompt is worded so the literal string `Exact Answer: UNKNOWN` **never appears in it**, and
the parser takes the **last** `Exact Answer:` line from `content`, falling back to `reasoning`
only if content has none — never concatenating the two. Without those guards, a model that
restates the format before answering has its own echo parsed as its answer and scores
`ABSTAINED` silently. `B2` measured 43 % of disputed parses carrying multiple `Exact Answer:`
strings; that detector is carried over here, and items with more than one match are counted and
printed rather than silently resolved.

**The headline is a floor, and it is a floor by construction.** Two independent choices push it
optimistically: the abstention match folds punctuation more permissively than the correctness
match (`abstain_key` vs `bare`), and last-match parsing favours a considered refusal over an
abandoned draft. Both convert borderline replies into `ABSTAINED` rather than `ANSWERED-WRONG`.
That direction is deliberate — scoring a genuine refusal as a confabulation would inflate the
number this tier exists to report — but it has to be stated every time the number is quoted:
**any surprise should be more confabulation than measured, never less.**

## What it reports

Three-way classification — `ABSTAINED` / `ANSWERED-CORRECT` / `ANSWERED-WRONG` — applied
**identically to both arms**. The previous grader folded *abstained* and *answered-wrong* into
one `FAIL` on the answerable arm, which is the single cell the 2×2 exists to separate.

| rate | definition |
|---|---|
| **confabulation** | answered on the unanswerable arm / 8 — **the headline** |
| **over-abstention** | refused on the answerable arm / 8 — the cost, and the timidity trap |
| accuracy | correct on the answerable arm / 8 — context for the other two |

Gate: **confabulation ≤ 3/8 and over-abstention ≤ 3/8**. Truncated items are excluded from the
2×2 and **void the run** — a truncated reply is a budget failure, never a failure to answer
(the lesson tier 2 already paid for at `n_predict=512`).

## This is a gate, not a measurement

16 items has **no power to detect a change** in calibration between two quants.
`../tier4/TIER3_INSTRUMENT_SELECTION.md` computed what a paired comparison actually costs: at
~15 % disagreement, a 70:30 discordant split needs ~47 discordant pairs ≈ **311 items**.

So this answers *"did confabulation blow up"*, not *"did it rise 4 points"*. **Do not quote a
delta from it.** The measurement corpus is a separate artifact and does not exist yet —
`BACKLOG A1`.

## Exposure

Two things here are asserted rather than verified, and both invert the item if wrong:

1. **Answerable golds** come from the author's knowledge, unchecked against a source. A wrong
   gold silently penalises a *correct* model.
2. **Unanswerable items are asserted to be unanswerable.** If "Halverstead", "Kellsworth",
   "Fairmount" or *The Winter Compass* turns out to name something real, the item begins
   punishing a model for knowing.

Both are recorded in `notes.known_weaknesses`. **Neither has been checked. Verify before any
of this is published**, and treat the first known-good run as a test of the fixture at least as
much as a test of the model.
