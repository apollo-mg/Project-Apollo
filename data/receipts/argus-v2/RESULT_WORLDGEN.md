# Result -- cardinality is now a dial, and that moves the bottleneck from items to templates

**2026-09-21.** Third piece of the day, and the one `RESULT_FIXTURE_COMPUTED_FAMILIES.md` named
as the blocker: *"the world holds 13 objects and exactly ONE referent-ambiguity instance, so
`worldgen.py` is the next piece of work."* No model was run.

**Prior art checked:** `ledger_precheck.py "generated synthetic world parameterized cardinality
item generation templates scale corpus" --deep` -> `A1_MEASUREMENT_CORPUS_SPEC.md`.
**What this adds:** A1 gives the construction (answerable = template on a member, unanswerable =
the identical template on a non-member) for **knowledge** sets. This transposes it to a **world**,
where the closed set is the fixture and membership is cardinality -- and then measures what the
transposition actually costs, which A1 could not know.

## What was built

`argus/worldgen.py` emits a world whose collision structure is a parameter, plus a corpus of
matched pairs generated against it.

```
$ worldgen.py --pairs 30 --singles 24 --today 2026-09-24
world   84 contacts (30 colliding forenames, 24 unique), 12 messages, 3 events
        cardinality plan verified: 54 forenames, 3 absent topics
corpus  54 items from 4 templates (8/template/arm)
        {'actions': 19, 'no_action_ask': 27, 'no_action': 8}
```

27 determined against 27 ask, **matched on template, phrasing and length by construction** --
only the world's cardinality differs. That is A1's design, and it is what makes the McNemar
pairing legitimate rather than a comparison of two differently-written item sets.

## Validation -- the independent path agrees, 54/54

The generator and `verify_families.py` are separate code: one places objects by *intent*
("this forename collides"), the other recomputes cardinality by *selector evaluation* against the
emitted JSON. Running the morning's verifier on the afternoon's output:

```
decidable          54/54
expectation agrees 54/54
matched pairs      t-false-sender 8/8   t-lookup-body 8/8
                   t-referent     8/8   t-unsat-event 3/3
clean -- every decidable expectation follows from the world
```

Byte-identical output from the same `--seed` across runs.

## A1's alias trap, mechanised -- and here it is strictly better

A1 names the one silent failure of closed-set construction: a non-member that is a member
**under another name**. `cassiopeium` is lutetium. Its remedy is a manual alias list, *"the
irreducible hand-work ... the only place the construction can quietly betray us."*

A generated world does not have that problem, because **the generator owns the name pool**. The
analogue is an unintended collision -- a forename meant to be unique that a second contact also
bears -- and it is both preventable and mechanically detectable. `_assert_cardinality` re-derives
every intended count from the emitted world using the same selectors the verifier uses, and
**refuses to write a world that does not match its own plan**.

`test_worldgen_collisions.py`, 5/5, because a plan check that passes on a correct plan has
demonstrated nothing (`[[readiness-probes-lie]]`):

| corruption | caught |
|---|---|
| a "unique" forename given a second bearer (the alias trap exactly) | yes |
| a colliding pair reduced to one -- the ask arm silently becomes determined | yes |
| an "absent" topic that exists -- unsatisfiable stops being unsatisfiable | yes |
| over-drawing the pool, which would reuse a name and forge a collision | raises |

**So A1's irreducible hand-work is reducible here.** That claim is specific to worlds and does not
transfer back to knowledge corpora, where no generator owns the entity set.

## The finding: the bottleneck moved, it did not disappear

I expected the world to be the constraint. It is not. **A1's own template cap is.**

> *"15 items from one template is a pattern a model can latch onto within a run ... Cap items per
> template (~8) and carry more templates (~60)."*

At 8 items per template per arm:

| target | templates needed | still to author |
|---:|---:|---:|
| 117/arm (if rungs reach 40 % discordance) | 15 | 11 |
| 240/arm (A1's original) | 30 | 26 |
| **374/arm (measured discordance)** | **47** | **43** |

**The generator converts a 374-item authoring problem into a 47-template one -- an 8x reduction,
not an elimination.** Templates remain the irreducible unit, which is exactly A1's "what stays
manual" list arriving in a different currency than expected. `worldgen.py` warns when
`--per-template` exceeds 8 rather than silently trading the cap for volume.

**And every template needs its own pool of distinct fillers**, which is a second, independent
bound. `t-unsat-event` produced 3 pairs, not 8, because its topic list holds 6 entries split
three present / three absent. The referent template is bounded by 59 forenames:

| target, referent-class only | distinct forenames if none may repeat |
|---:|---:|
| 117/arm | 234 |
| 240/arm | 480 |
| 374/arm | **748** |

Whether names *may* repeat across templates is a real decision, not an oversight. Reuse is
defensible -- the world is the world, and an agent that learns "Priya is unambiguous" has learned
a true fact **by looking**, which is the behaviour the corpus wants. The risk is the other route
to that fact: within-run memorisation that skips the lookup. `min_calls` already catches the
ungrounded version of it, so this is a leak worth measuring rather than an obvious defect.
**Undecided, and flagged rather than settled.**

## What this does NOT establish

- **No model has run against a generated corpus.** Every number here is a property of the
  generator and the verifier.
- **Four templates is a demonstration, not a corpus.** The 54 items exist to prove the machinery;
  they do not constitute an instrument.
- **A1's "check per-template outcome variance" is not done.** A1 warns that if per-template
  outcomes are near-identical the corpus measures templates rather than judgement. That check
  needs run data and is the first thing to do with it. The generator emits `template` on every
  item so the check is possible; nothing yet performs it.
- **Phrasing variants are unvalidated.** Eight surface forms per template are carried on the
  assumption they reduce the template tell. Untested, as A1 says of the same idea.
- **The generated world is simpler than the hand-built one.** No attendee structures, no label
  variety, one file. Items that need those (`f3-scope`, `f6-inconsistent`, `f8-time`) have no
  generator template yet, and three of those families are the ones with undecidable rungs anyway.
