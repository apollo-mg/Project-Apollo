#!/usr/bin/env python3
"""Shift a fixture's absolute dates so its intended "today" lands on the run date.

WHY THIS EXISTS: seed.json hardcodes 2026-08-27. Run it on the 26th and "clear my afternoon"
finds an EMPTY calendar -- the model cannot act destructively even if it wants to, so it scores
clean for free. That is exactly what happened: a four-arm n=12 comparison (25% vs 83%, p=0.012)
was measuring calendar emptiness, not abstention. Void, and not detectable from the verdicts.

Whole-day shift preserves every intra-fixture relationship (message 8 days before the events,
file modified 9 days before, second event the following morning). Weekday names appearing in
text are rewritten to match, or "Thursday sync" lands on a Tuesday and the prose lies.
"""
import argparse, json, re, sys
from datetime import datetime, timedelta, timezone

ANCHOR = datetime(2026, 8, 27, tzinfo=timezone.utc)   # the day this seed was authored FOR
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}:\d{2})(Z|[+-]\d{2}:\d{2})?")
DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def shift_str(s, delta):
    def rep(m):
        d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc) + delta
        return f"{d:%Y-%m-%d}T{m.group(4)}{m.group(5) or ''}"
    return ISO.sub(rep, s)

def walk(o, delta):
    if isinstance(o, str):  return shift_str(o, delta)
    if isinstance(o, list): return [walk(x, delta) for x in o]
    if isinstance(o, dict): return {k: walk(v, delta) for k, v in o.items()}
    return o

def main(a):
    d = json.load(open(a.seed))

    # IDEMPOTENCE. delta was computed from the hardcoded ANCHOR and applied to the seed's
    # CURRENT dates, so rebasing an already-rebased seed shifted it AGAIN. make_fixture.sh
    # passes --force, which skipped the only guard, and on 2026-09-21 that moved the
    # Thursday sync to 2026-10-19 -- a Monday, which the weekday fixer below then renamed
    # to "Monday sync", making the corruption look deliberate. verify_families.py caught
    # it: 4 items inverted and 3 family boundaries moved, including f5-conflict-r3, whose
    # Friday collision vanished and which flipped from "ask" to "act".
    prev = d.get("_rebased", {}).get("to")
    base = (datetime.strptime(prev, "%Y-%m-%d").replace(tzinfo=timezone.utc) if prev else ANCHOR)

    if a.date:
        target = datetime.strptime(a.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        # WEEKDAY SNAP. The fixture is weekday-anchored: "Thursday sync", "Friday 1:1",
        # and clauses in families_v3.json that select on weekday. ANCHOR is a Thursday, so
        # rebasing to an arbitrary "today" lands a Thursday event on whatever day it is and
        # silently breaks every weekday-anchored item. FAILURE_MODES already records this
        # as preconditions needing to be JOINTLY satisfiable, noting the corpus "is only
        # fully satisfiable one day a week". Snapping to the anchor's own weekday makes that
        # true every day instead.
        now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        ahead = (ANCHOR.weekday() - now.weekday()) % 7
        target = now + timedelta(days=ahead)

    delta = target - base
    if delta.days == 0 and not a.force:
        print(f"already anchored to {target:%Y-%m-%d}; nothing to do"); return 0
    if delta.days == 0:
        print(f"already anchored to {target:%Y-%m-%d} (--force: rewriting in place)")
    out = walk(d, delta)
    # Fix weekday prose: an event whose summary names its OLD weekday must name the new one.
    for ev in out.get("events", []):
        old = next((e for e in d.get("events", []) if e["id"] == ev["id"]), None)
        if not old: continue
        ow = DAYS[datetime.strptime(old["start"][:10], "%Y-%m-%d").weekday()]
        nw = DAYS[datetime.strptime(ev["start"][:10], "%Y-%m-%d").weekday()]
        if ow != nw:
            ev["summary"] = re.sub(rf"\b{ow}\b", nw, ev.get("summary", ""))
    out["_rebased"] = {"anchor": f"{ANCHOR:%Y-%m-%d}", "to": f"{target:%Y-%m-%d}", "days": delta.days}
    for p in a.write or [a.seed]:
        json.dump(out, open(p, "w"), indent=2)
    print(f"rebased {delta.days:+d}d  ({base:%Y-%m-%d} -> {target:%Y-%m-%d}, "
          f"{target:%A})  "
          f"events now: {[ (e['id'], e['start'][:16], e['summary']) for e in out.get('events',[]) ]}")
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("seed"); p.add_argument("--date"); p.add_argument("--force", action="store_true")
    p.add_argument("--write", nargs="*", help="output paths (default: in place)")
    sys.exit(main(p.parse_args()))
