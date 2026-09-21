#!/usr/bin/env python3
"""Is an item's ambiguity visible from EVERY retrieval path, or only one?

`f1-referent-r3` ("Email Dave") is ambiguous because two contacts match
/\bdave\b/. But the two Daves collide on `name` ONLY: Okafor's address is
`d.okafor@`, not `dave.okafor@`, so an agent that searches mail or calendar for
"dave" finds exactly ONE hit and can act on sound reasoning -- and be scored
WRONG for it.

A clause evaluated on one set cannot see this. An item is robustly ambiguous
only if every plausible path agrees, so this walks the same key across contacts,
messages and events and reports disagreement.

This is a CORPUS check, not an agent check: it says whether an item can be
scored fairly, not whether a model got it right.
"""
import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import world_facts as wf  # noqa: E402

# the paths an agent can plausibly take to resolve a person reference
PATHS = [
    ("contacts", lambda k: {"set": "contacts", "where": {"name_matches": k}}),
    ("messages", lambda k: {"set": "messages", "where": {"from_matches": k}}),
    ("events",   lambda k: {"set": "events",   "where": {"has_attendee": k}}),
]


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default=str(Path(__file__).parent / "families_v3.json"))
    ap.add_argument("--world", default=str(Path(__file__).parent / "fake-google/fixtures/seed.json"))
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    world = json.load(open(a.world))
    scs = json.load(open(a.families))["scenarios"]

    bad = []
    print("Items whose clause selects PEOPLE, evaluated across every retrieval path:\n")
    for sc in scs:
        for cl in sc.get("decided_by", []):
            sel = cl["selector"]
            where = sel.get("where", {})
            key = where.get("name_matches") or where.get("from_matches") or where.get("has_attendee")
            # only person-reference clauses with a single key are comparable across paths
            if not key or len(where) != 1 or sel["set"] not in ("contacts", "messages", "events"):
                continue
            counts = {name: len(wf.select(world, mk(key), today)) for name, mk in PATHS}
            amb = {n: (c > 1) for n, c in counts.items()}
            disagree = len(set(amb.values())) > 1
            flag = "  <-- PATH-DEPENDENT" if disagree else ""
            print(f"  {sc['id']:22} {cl.get('role',''):24} key={key!r}")
            print(f"  {'':22}   " + "  ".join(f"{n}={c}" for n, c in counts.items()) + flag)
            if disagree:
                bad.append((sc["id"], key, counts))

    print(f"\n{len(bad)} clause(s) are path-dependent.")
    if bad:
        print("An agent taking a different-but-valid path sees a different cardinality,")
        print("so these items cannot be scored fairly as written:")
        for sid, key, counts in bad:
            print(f"   {sid:22} {key!r}  {counts}")
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
