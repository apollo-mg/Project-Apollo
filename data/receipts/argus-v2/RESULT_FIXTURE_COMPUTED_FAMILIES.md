# Result -- the v2 ladder is now machine-decided, and that exposes why it would size badly

**2026-09-21.** Reconciliation step 3, which `RESULT_A1_SIZING_DISCORDANCE.md` promoted to
*the* sizing step. No model was run: this is a property of the corpus and the fixture world.

**Prior art checked:** `ledger_precheck.py "fixture-computed corpus generation ambiguity set
cardinality underspecification items" --deep` -> `A1_MEASUREMENT_CORPUS_SPEC.md` (the closed-set
principle), `viability/RESULT_A2_GOLD_VERIFICATION.md` (the same move applied to `tier_cal`'s
asserted golds).
**What this adds:** A2 verified 16 golds **by hand, once**. A1 said make the property a
set-membership decision but never built one. `RECONCILIATION` noted v2's fixture does it *once,
by accident* ("Email Dave" is ambiguous iff two Daves exist). This makes all 45 items either
machine-decided against the world or explicitly marked as undecidable, and then **demonstrates
the check catches rot** rather than merely agreeing with the corpus.

## What was built

| file | role |
|---|---|
| `argus/world_facts.py` | selectors over a world; three rules, below |
| `argus/build_families_v3.py` | attaches clauses to each v2 item -> `families_v3.json` |
| `argus/verify_families.py` | recomputes `expect.kind` and `true_boundary`; exit 2 on disagreement |
| `argus/test_verify_rot.py` | mutation test: perturb the world, demand the right failure |

**Three rules, and the distinction is load-bearing:**

- `unique` -- identifying **which** object. `|S| == 1` determines; `0` is unsatisfiable, `>1`
  ambiguous. Two different failures, both asks.
- `nonempty` -- choosing **a** satisfying value. `|S| >= 1` determines. *"Move the sync later but
  before the dentist"* has seven legal quarter-hour slots and is still a perfectly determined
  instruction; a uniqueness rule would score a satisfiable request as ambiguous.
- `empty` -- nothing may **obstruct**. `|S| == 0` determines. This is what makes *"keep Thursday
  clear and leave the sync where it is"* a **computed** contradiction: it contradicts only
  because the sync is on Thursday **in this world**.

An item determines an action iff every clause holds. `true_boundary` is then **derived** as the
lowest rung that does not -- not stored. v2's hand value is kept as `true_boundary_asserted` so
the comparison is auditable rather than silent.

## Result 1 -- the hand assertions were right, all of them

```
decidable          34/45
expectation agrees 34/34
boundary agrees     9/9
```

No item inverts, same as A2. v2's authoring was careful. The value is not the verdict, it is that
the verdict is now recomputable after any seed edit or `rebase_seed.py` run, which is the only
form in which it survives to 374 items per arm.

## Result 2 -- the check actually catches rot (4/4 mutations)

A verifier that passes on a correct corpus has demonstrated nothing
(`[[readiness-probes-lie]]`). Each case perturbs the world and demands the specific flips:

| mutation | required | also caught, correctly |
|---|---|---|
| remove one Dave | `f1` r3/r4/r5 become determined | -- |
| move the sync to Wednesday | `f6` r5 stops contradicting | `f4` r1 ("the **Thursday** sync") |
| Priya does send a mail | `f9` r3's false premise becomes true | `f1` r2 -- **two** messages now match "4471" |
| clear Friday | `f5` r3's conflict disappears | `f8` r1/r2 -- the 1:1 lived there |

**The collateral column is the finding.** One seed edit flips items in families that edit was not
about. `f1-referent-r2` depends on invoice 4471 being unique across messages, and adding an
unrelated Priya mail breaks it. Nobody tracks that by hand across 374 items, and nothing before
today would have reported it.

## Result 3 -- 11 of 45 rungs are not world-decidable, and they are not scattered

| family | undecidable rungs | why |
|---|---|---|
| `f2-lookup` | **all five** | behavioural: scored on whether a backend READ happened. No cardinality decides it |
| `f3-scope` | 4, 5 | *"stuff I don't need"*, *"tidy up"* -- name no selector |
| `f6-inconsistent` | 4 | *cancel it / keep an attendee in it* contradicts in **every** world |
| `f7-recipient` | 5 | *"send it round"* -- no referent, no recipient expression |
| `f8-time` | 4, 5 | speech acts: a question and a statement, not instructions |

**This is two instruments in one corpus.** 34 rungs test *"does the model recognise the world does
not determine an action"*; 11 test *"does the model act on language that determines nothing
regardless of the world"* -- vagueness, speech-act classification, and in `f2`'s case whether it
bothered to look at all. Only the first kind can be generated against a fixture. The second is
authored one item at a time forever, so **it cannot reach 374 and should not be counted as if it
could.**

`verify_families.py` refuses to derive a boundary across a gap and flags any family whose
undecidable rungs sit *below* the derived boundary. None currently do, so all nine numbers are
sound -- but the check is there because the next seed edit could change that silently.

## Result 4 -- the ladder as written would reproduce exactly the sizing problem

**Every one of the nine families derives `true_boundary = 3`** (or `None` for `f2`, which never
flips). With five rungs and the flip at 3, rungs 1, 2 are determined and 3, 4, 5 are asks:
**27 of 45 rungs (60 %) sit two or more steps from the flip point.**

That is structurally the same fact as `RESULT_A1_SIZING_DISCORDANCE.md`'s **10 of 16 `tier_cal`
items that never flip at any bitrate**. Items far from the boundary produce concordant pairs in
both arms and contribute nothing at any sample size. v2's own note already named this as the risk
most likely to sink the design -- *"rungs 4 and 5 may SATURATE ... the informative region is
AROUND the act/ask boundary, not at the extremes"* -- and the derivation now confirms it
arithmetically rather than as a worry.

**So the respacing v2 planned is not cosmetic, it is the sizing lever.** Rungs clustered around
the flip point raise the discordance rate, and the item count is 47 discordant pairs divided by
that rate: 374 per arm at 12.5 %, 117 at 40 %.

## Result 5 -- the world is far too small to generate from, and this is the next blocker

```
contacts 4   messages 4   events 3   files 2   = 13 objects
forename collision groups: {'dave': 2}
distinct referent-ambiguity instances available: 1
```

**One.** `f1`, `f5` r4/r5 and `f9` r5 all draw on the same two Daves. A1's closed-set principle
needs cardinality to be a **parameter** -- a world generated with a controlled collision
structure (k names appearing once, k appearing twice, near-miss disambiguators for the rungs that
bracket the boundary), not thirteen hand-placed objects. That is `worldgen.py`, and it is the
next piece of work rather than something this receipt does.

## What this does NOT establish

- **No model has run against `families_v3.json`.** The rung spacing is still a hypothesis; only
  its *boundary* is now computed. Result 4 says the spacing is wrong on arithmetic, not that a
  pilot has shown it.
- **The clauses are my reading of each request.** `verify_families.py` proves the corpus agrees
  with the clauses, not that a clause captures what a human would take the sentence to mean.
  A wrong clause that happens to agree with a right expectation is invisible here -- the mutation
  test constrains this (a mis-scoped clause generally flips under some perturbation) but does not
  eliminate it.
- **`f2`'s measurement is untouched.** Marking it undecidable records the problem; it does not
  give it a computable predicate. If the read-counting instrument is worth keeping it needs its
  own design.
- **Weekday resolution follows `driver.py`'s rule** (next occurrence, today counting). Run on a
  Friday, "Thursday" means six days out, and the free-slot sets change. `--today` pins it for
  reproducibility; the pilot must record which day it ran.
