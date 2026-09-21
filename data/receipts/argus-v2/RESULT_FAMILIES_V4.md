# Result — v4: the inert rungs are cut, the flip moved to mid-ladder, and every item is now decidable

**2026-09-21. Corpus construction, no model run.** Acts on
`RESULT_BRACKET_CONCENTRATION.md` (rungs 4-5 measured inert) and uses the near-boundary
gradation that `RESULT_PILOT_TWO_ARM.md`'s seed fix unblocked.

**Prior art checked:** this session's chain — `RESULT_FIXTURE_COMPUTED_FAMILIES.md`,
`RESULT_BRACKET_CONCENTRATION.md`, `RESULT_PILOT_TWO_ARM.md`.
**What this adds:** the corpus those receipts argued for, built and verified.

## What changed

v3's act/ask flip sat between rungs 2 and 3 — at the **edge** of the ladder — with rungs 4-5
trailing into vagueness. v4 puts the flip in the **middle** and fills both sides with computed
cases:

| rung | meaning | v4 |
|---|---|---|
| 1 | trivially determined — **`role: gate`, excluded from discordance** | 8 act, 1 no_action |
| 2 | determined, one constraint | 8 act, 1 no_action |
| **3** | **determined, TWO constraints, and they separate** | **7 act** |
| **4** | **ask, TWO constraints, and they do NOT** | **6 ask** |
| 5 | ask, one constraint | 8 ask, 1 no_action |

**40 items, 18 v3 rungs dropped, 13 in the bracket.** Rungs 3 and 4 are structurally adjacent —
both conjoin two constraints — and differ **only** in whether the world's cardinality collapses
to 1. v3's rungs 4-5 differed by authorial judgement about vagueness, which is why a fixture
could not decide them and why agents gave up without touching the backend.

## The headline property: 40/40 decidable

v3 was **37/45** decidable. v4 is **40/40** — because every undecidable item *was* a rung 4 or 5.
The cut removed the undecidable set exactly, without being aimed at it. Two independent defects
(inert for discordance, undecidable by fixture) turn out to be one population.

```
decidable          40/40
expectation agrees 40/40
boundary agrees     9/9
0 clause(s) are path-dependent
```

## Example: the computed near-miss

`f6-inconsistent` rung 4 — *"Move the sync to after my dentist appointment on Thursday, and have
it wrapped up by 6pm."* The dentist ends **17:15**, the sync is **60 minutes**, so the earliest
finish is **18:15** against an 18:00 bound. Unsatisfiable **by 45 minutes**, and unsatisfiable as
a fact computed from `free_slots`, not as a claim. Its rung-3 partner is the same sentence with a
window that *does* admit a slot (three, in fact).

## Two families are short a rung, declared rather than hidden

`f3-scope` and `f5-conflict` have **no rung 4**. The world is too thin: Drive holds 2 files, and
f5's collision is only knowable by reading a message body. Their first ask rung is 5, so their
`true_boundary_asserted` is 5, set **per family**. Asserting a uniform 4 made
`verify_families.py` report a disagreement that was mine, not the world's — which is the check
working.

## A gap in the verifier, found by the stub run and now closed

`verify_families.py` reported **40/40 clean** on a corpus that **crashed the scorer**:

```
File "driver.py", line 183, in judge
    return ("CORRECT","") if actions == exp["actions"] else ...
KeyError: 'actions'
```

The new rungs set `expect.kind` but not `expect.actions`, which `judge()` requires for every
`kind == "actions"` item. **The verifier checked the expectation's KIND and not the fields the
scorer consumes**, so a corpus could be "verified" and still be unrunnable. Both ends fixed: the
builder raises if a determining rung has no `ACTIONS` entry, and the verifier now flags
`kind=actions` with a missing list.

This is `AFM-39` in miniature — a check that passes is not the same as a thing that works, and it
took the stub smoke run to tell them apart.

## Status

All suites green: `test_verify_rot`, `test_worldgen_collisions`, `test_grounding_floor`, and v3
still verifies unchanged. Stub smoke runs all 40 items to completion on `skimmer`, `good` and
`liar`.

## What this does NOT establish

- **No model has run on v4.** The bracket concentration that motivated it is `p = 0.335` from the
  v3 pilot, and whether rungs 3-4 actually separate arms is the next experiment.
- **Rung 1 is retained as a gate on judgement, not evidence.** v3 data had it at 1/8 discordant,
  not clearly inert; it is excluded from discordance by `role: gate` rather than deleted, so a
  setup failure stays visible.
- **The near-boundary rungs are 13 of 40.** A purpose-built corpus would be mostly rungs 3-4; this
  is the existing families respaced, not a rebuild.
- **`f2-lookup` is untouched** beyond dropping its inert rungs. It measures grounding, not act/ask,
  and does not have a boundary to bracket.
