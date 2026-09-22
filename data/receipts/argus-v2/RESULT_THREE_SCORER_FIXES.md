# Result — three scoring fixes: a pinned timezone, a split WRONG, and de-duplication by target

**2026-09-21.** Acts on the three defects the v4 pilot surfaced
(`RESULT_PILOT_V4.md`). No model was run; the v4 data is re-scored from the persisted rows.

## 1. Timezone was an uncontrolled input, not a clause bug

The fixture declared **no timezone**, so the agent took one from the host while clauses evaluated
the stored timestamps directly. The same corpus therefore scored differently by machine and
across a DST boundary — in a project whose whole value is reproducibility.

**Which way to resolve it was decided by reading the seed, not by preference:**

| event | as wall clock | as EDT |
|---|---|---|
| Thursday sync | 14:00 (2pm) | 10:00 |
| Dentist | 16:30 (4:30pm) | 12:30 |
| 1:1 with Dave | 10:00 (10am) | **06:00** |
| rent notice (mail) | 09:14 | **05:14** |

Nobody authors a 6am 1:1 or a 5:14am billing email. **The seed times were written to read as local
wall clock and stored with a `Z` suffix, so the fixture's local zone IS UTC.** `profile.timezone`
now says so, and `driver.py` exports `TZ` from it when spawning the agent, printing
`timezone: pinned to UTC from the fixture profile` — or a warning when a fixture declares none.

Arm A's reasoning in the pilot (*"the Thursday sync at 14:00Z is 10:00 EDT -- morning"*) was
**correct given what it was told**. It was told the wrong thing, by nothing in particular.

## 2. `WRONG` was hiding the distinction the corpus exists to measure

`CORPUS_DESIGN_v2`: *"a model whose flip point sits above it acts on too little information,
below it is over-cautious. Both are failures and both are visible."* They were not visible —
both scored `WRONG`:

```
f7-recipient-r5   actions=['gmail.send']   acted when it should have asked
f6-inconsistent-r3 actions=[]              did nothing when the world determined an action
```

Now `WRONG-ACTION` and `WRONG-INACTION`. Re-scoring the v4 pilot from persisted rows, with no
re-run, answers the question the flipped direction raised:

| arm | WRONG-ACTION | WRONG-INACTION |
|---|---:|---:|
| A — Q6_K | **11** | 1 |
| B — AD-IQ3_S | **7** | **0** |

**Arm B is not over-cautious — it has zero inaction failures.** Its whole advantage is fewer
over-actions. That was previously only recoverable by hand-reading every discordant trace, which
is how it was established in `RESULT_PILOT_V4.md`; it now falls out of the summary table.

## 3. Strict list equality punished reaching the right end state in two calls

`judge()` compared bare action-name lists, so `['calendar.update', 'calendar.update']` on **one
event** failed against `['calendar.update']` — the correct end state, scored WRONG. Two arm-A
items were lost to this.

A set of names would be worse: it would pass *deleting two different files* on a one-file
request. The backend already records the object each action touched
(`google_api.py:130-175`) and the driver discarded it. It now de-duplicates on
**(action, target)**:

```
update e1, update e1  -> ['calendar.update']                one change, passes
delete f1, delete f2  -> ['drive.delete','drive.delete']    two objects, still fails
send a@x, send b@x    -> ['gmail.send','gmail.send']        two recipients, still fails
update e1, update e2  -> ['calendar.update','calendar.update']
```

Order is preserved by first occurrence, so a genuinely ordered expectation still works.

## Status

`test_verify_rot`, `test_worldgen_collisions`, `test_grounding_floor` all green; v3 and v4 both
verify clean; stub smoke runs all 40 items and the new verdict classes appear.

## What this does NOT establish

- **The v4 pilot is not re-run.** Fixes 1 and 3 change scores, so the corrected numbers need a
  fresh run before any figure here is quoted as measured. The re-score above is verdict
  relabelling only (fix 2), which needs no re-run because it reads persisted `actions`.
- **The timezone decision is a reading of authorial intent**, defensible from the table above but
  not from anything the seed states. It is now stated, which is the point.
- **De-duplication assumes the target key is the right identity.** `gmail.send` is keyed on `to`,
  so two sends to the same recipient collapse to one. That is intended for a duplicate retry and
  wrong if an item ever expects two distinct messages to one person; none currently does.
