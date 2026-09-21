#!/usr/bin/env python3
"""The generator must refuse to emit a world that violates its own plan.

A1 names the one way closed-set construction fails silently: a non-member that is
a member under another name.  For a knowledge corpus the defence is a manual
alias list.  For a generated world the generator owns the name pool, so the
defence can be mechanical -- but only if it actually fires.  A plan check that
passes on a correct plan has demonstrated nothing (`[[readiness-probes-lie]]`).

Each case corrupts the pool so an intended cardinality is wrong, and demands the
generator refuse.
"""
import datetime as dt
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import worldgen as wg  # noqa: E402

TODAY = dt.date(2026, 9, 24)


def build(pairs=6, singles=6):
    rng = random.Random(7)
    random.seed(7)
    w = wg.build_world(rng, pairs, singles, TODAY)
    return w, wg._assert_cardinality(w, TODAY)


def case_clean():
    _, bad = build()
    return not bad, "clean world emits no complaint", bad


def case_singleton_duplicated():
    """A 'unique' forename given a second bearer -- the alias trap, exactly."""
    w, _ = build()
    f = w["_plan"]["single"][0]
    w["contacts"].append({"id": "cX", "name": f"{f} Interloper", "email": "x@t.test"})
    bad = wg._assert_cardinality(w, TODAY)
    return (any(f in b and "unique" in b for b in bad),
            f"duplicating singleton {f!r} is caught", bad)


def case_collision_broken():
    """A colliding pair reduced to one bearer -- the ask arm silently becomes determined."""
    w, _ = build()
    f = w["_plan"]["collide"][0]
    hit = next(c for c in w["contacts"] if c["name"].startswith(f + " "))
    w["contacts"].remove(hit)
    bad = wg._assert_cardinality(w, TODAY)
    return (any(f in b and "collide" in b for b in bad),
            f"breaking collision {f!r} is caught", bad)


def case_absent_topic_present():
    """An 'absent' topic that exists -- the unsatisfiable arm stops being unsatisfiable."""
    w, _ = build()
    t = w["_plan"]["topics_absent"][0]
    w["events"].append({"id": "eX", "summary": f"{t.capitalize()} meeting",
                        "start": f"{TODAY}T09:00:00Z", "end": f"{TODAY}T10:00:00Z",
                        "attendees": [], "calendar": "primary"})
    bad = wg._assert_cardinality(w, TODAY)
    return (any(t in b for b in bad), f"present 'absent' topic {t!r} is caught", bad)


def case_pool_exhausted():
    """Over-drawing the pool must fail loudly, not reuse a name and create a collision."""
    try:
        build(pairs=len(wg.FORENAMES), singles=10)
        return False, "over-drawing the forename pool raises", ["no exception"]
    except SystemExit as e:
        return "pool holds" in str(e), "over-drawing the forename pool raises", [str(e)[:70]]


def main():
    ok = True
    for fn in (case_clean, case_singleton_duplicated, case_collision_broken,
               case_absent_topic_present, case_pool_exhausted):
        good, name, detail = fn()
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name}")
        if not good:
            print(f"        got: {detail}")
    print(f"\n{'generator refuses every corrupted plan' if ok else 'A CORRUPTED PLAN WAS EMITTED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
