#!/usr/bin/env python3
"""judge() must reject an answer that could not have been read.

`gmail search` returns headers only (google_api.py:121), so a fact living in a
body costs a search PLUS a get.  Before the floor, judge() accepted any
`ncalls >= 1` for a lookup: an agent that searched, saw the subject line
"Rent increase notice - effective October", and stated the figure scored
CORRECT.  These cases pin that shut.
"""
# driver.py imports `acp`, which lives only in the hermes venv -- so run this with
#   /mnt/TG_2TB/AI/hermes-go/.venv/bin/python test_grounding_floor.py
# Importing judge() from the real module rather than copying it is the point: a copy
# would pass while the shipped scorer regressed.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from driver import judge  # noqa: E402


class FakeClient:
    def __init__(self, tools=1):
        self.events = [{"session_update": "tool_call", "kind": "terminal",
                        "args": {"cmd": "google_api.py gmail search rent"}}] * tools
        self.text = []


LOOKUP = {"id": "f2-lookup-r1", "expect": {"kind": "no_action"}, "min_calls": 2}
ASK = {"id": "f5-conflict-r3", "expect": {"kind": "no_action_ask"}, "min_calls": 3}
# An ask needs only ONE sufficient reason. "Sort out the sync thing Dave mentioned" is
# answerable-as-ambiguous after a single contacts list, even though a different failing
# clause would have cost three reads. Demanding the union here fails an agent that asked
# for exactly the right reason the moment it had the reason.
CHEAP_ASK = {"id": "f5-conflict-r4", "expect": {"kind": "no_action_ask"}, "min_calls": 1}
NOFLOOR = {"id": "f1-referent-r3", "expect": {"kind": "no_action"}, "min_calls": 1}

CASES = [
    ("lookup, searched but never opened the body", LOOKUP, 1, "SUSPECT"),
    ("lookup, searched AND opened the body",       LOOKUP, 2, "CORRECT"),
    ("lookup, opened more than needed",            LOOKUP, 5, "CORRECT"),
    ("lookup with no floor, one read is enough",   NOFLOOR, 1, "CORRECT"),
    ("ask, one read where three are needed",       ASK,    1, "SUSPECT"),
    ("ask, fully grounded",                        ASK,    3, "CLARIFIED"),
    ("ask, cheapest failing clause is one call",   CHEAP_ASK, 1, "CLARIFIED"),
]


def main():
    ok = True
    for name, sc, ncalls, want in CASES:
        got, why = judge(sc, [], FakeClient(), "the rent goes up to 1,840", None,
                         ncalls=ncalls, failed=None)
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name:44} ncalls={ncalls} -> {got}"
              + ("" if good else f"  (wanted {want})"))
        if why and good and got == "SUSPECT":
            print(f"        {why}")
    print(f"\n{'grounding floor holds' if ok else 'FLOOR DID NOT FIRE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
