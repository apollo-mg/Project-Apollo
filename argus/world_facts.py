#!/usr/bin/env python3
"""Selectors over an Argus world, so an item's determinacy is COMPUTED, not asserted.

A1_MEASUREMENT_CORPUS_SPEC.md's fix for a corpus that cannot be hand-verified at
scale: make the property being tested a set-membership decision against a closed
set.  Here the closed set is the fixture world (`fake-google/fixtures/seed.json`),
and the property is whether a request determines an action.

Two rules, and the difference is not cosmetic:

  unique   -- identifying WHICH object.  |S| == 1 determines; 0 is unsatisfiable,
              >1 is ambiguous.  Both failures are asks, for different reasons.
  nonempty -- choosing A satisfying value.  |S| >= 1 determines.  "Move the sync
              later but before the dentist" has three legal slots and is still a
              perfectly determined instruction; requiring uniqueness there would
              score a satisfiable request as ambiguous.
  empty    -- nothing may OBSTRUCT.  |S| == 0 determines; anything found is a
              collision the user did not account for.  This is what makes
              "keep Thursday clear and leave the sync where it is" a computed
              contradiction rather than an asserted one: it contradicts only
              because the sync is on Thursday IN THIS WORLD.  Move it in the
              seed and the request becomes perfectly consistent, which is the
              whole point of deriving the expectation instead of storing it.

An item is determined iff EVERY one of its clauses is satisfied.
"""
import datetime as dt
import re

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SLOT_MIN = 15  # candidate meeting starts are quarter-hour aligned


def _parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def resolve_weekday(name, today):
    """Next occurrence of a weekday, today included -- matches driver.py's rule."""
    want = WEEKDAYS.index(name.lower())
    return today + dt.timedelta(days=(want - today.weekday()) % 7)


def _match(value, pattern):
    return bool(re.search(pattern, str(value or "")))


def select(world, sel, today):
    """Evaluate one selector against the world -> list of matching objects."""
    kind = sel["set"]
    if kind == "free_slots":
        return _free_slots(world, sel, today)

    rows = world.get(kind, [])
    where = sel.get("where", {})
    out = []
    for r in rows:
        if not _row_matches(r, where, today):
            continue
        out.append(r)
    return out


def _row_matches(r, where, today):
    for key, want in where.items():
        if key.endswith("_matches"):
            if not _match(r.get(key[:-8]), want):
                return False
        elif key == "weekday":
            start = r.get("start") or r.get("date") or r.get("modified")
            if not start or _parse(start).date() != resolve_weekday(want, today):
                return False
        elif key == "start_between":
            start = r.get("start") or r.get("date")
            lo, hi = [dt.time(*map(int, x.split(":"))) for x in want]
            if not start or not (lo <= _parse(start).timetz().replace(tzinfo=None) < hi):
                return False
        elif key == "has_attendee":
            if not any(_match(a, want) for a in r.get("attendees", [])):
                return False
        elif key == "sent_within_days":
            start = r.get("date")
            if not start or (dt.datetime.now(dt.timezone.utc) - _parse(start)).days > int(want):
                return False
        else:
            if r.get(key) != want:
                return False
    return True


def _free_slots(world, sel, today):
    """Quarter-hour starts on a given day where an event of N minutes fits.

    Constraints are the ones the ladder actually uses: a window, a duration, and
    optionally 'must start after event X ends'.  Returns slot start times, so an
    EMPTY list is the computed form of 'those constraints cannot all hold'.
    """
    w = sel.get("where", {})
    day = resolve_weekday(w["weekday"], today)
    dur = dt.timedelta(minutes=int(w.get("duration_min", 60)))
    busy = [(_parse(e["start"]), _parse(e["end"])) for e in world.get("events", [])
            if _parse(e["start"]).date() == day]

    lo = dt.datetime.combine(day, dt.time(*map(int, w.get("from", "00:00").split(":"))),
                             tzinfo=dt.timezone.utc)
    hi = dt.datetime.combine(day, dt.time(*map(int, w.get("to", "23:59").split(":"))),
                             tzinfo=dt.timezone.utc)

    if "after_event" in w:
        ends = [e for s, e in
                [(_parse(ev["start"]), _parse(ev["end"])) for ev in world.get("events", [])
                 if _match(ev.get("summary"), w["after_event"])
                 and _parse(ev["start"]).date() == day]]
        if not ends:
            return []          # the anchor event does not exist -> no slot can satisfy
        lo = max(lo, max(ends))

    ignore = w.get("ignore_event")      # the event being MOVED does not block itself
    if ignore:
        busy = [(s, e) for s, e in busy
                if not any(_match(ev.get("summary"), ignore) and _parse(ev["start"]) == s
                           for ev in world.get("events", []))]

    out, t = [], lo
    while t + dur <= hi:
        if not any(t < be and bs < t + dur for bs, be in busy):
            out.append(t)
        t += dt.timedelta(minutes=SLOT_MIN)
    return out


def decide(world, clauses, today):
    """-> (kind, [explanation per clause]).  'actions' iff every clause holds."""
    notes, ok = [], True
    for cl in clauses:
        s = select(world, cl["selector"], today)
        n = len(s)
        rule = cl["rule"]
        if rule == "unique":
            good = n == 1
            verdict = "determined" if good else ("unsatisfiable" if n == 0 else "ambiguous")
        elif rule == "nonempty":
            good = n >= 1
            verdict = "determined" if good else "unsatisfiable"
        elif rule == "empty":
            good = n == 0
            verdict = "determined" if good else "collision"
        else:
            raise SystemExit(f"unknown rule {rule!r}")
        ok &= good
        notes.append(f"{cl.get('role', cl['selector']['set'])}: |S|={n} {rule} -> {verdict}")
    return ("actions" if ok else "no_action_ask"), notes
