#!/usr/bin/env python3
"""families_v4: cut the inert rungs, respace the survivors around the act/ask flip.

WHY. `RESULT_BRACKET_CONCENTRATION.md` measured what
`RESULT_FIXTURE_COMPUTED_FAMILIES.md` predicted before any model ran: rungs 4-5
produced 9 scorable items, ZERO discordant pairs and 5 of the 7 voids, while the
bracketing rungs ran 18.8% discordant against 5.9% outside. Rungs 4-5 are not
weak signal, they are no signal at a cost.

THE RESPACING. v3's flip sat between rungs 2 and 3, i.e. at the EDGE of the
ladder, with rungs 4-5 trailing off into vagueness a fixture cannot decide. v4
puts the flip in the MIDDLE and fills both sides of it with computed cases:

    1  gate       trivially determined -- a setup check, NOT scored
    2  determined   one constraint, unique
    3  determined   TWO constraints, and they separate        <- new
    4  ask          TWO constraints, and they do NOT          <- new
    5  ask          one constraint, ambiguous / unsatisfiable

Rungs 3 and 4 are structurally adjacent -- both conjoin two constraints -- and
differ ONLY in whether the world's cardinality collapses to 1. That is a
computed distinction. v3's rungs 4-5 differed by authorial judgement about
vagueness, which is why a fixture could not decide them and why agents gave up
without touching the backend.

Ids are reused across versions with DIFFERENT content: v3's `f1-referent-r3` is
not v4's. Compare by file, never by id alone.

Every selector here was verified numerically against the seed before the request
text was written, not after.
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import world_facts as wf  # noqa: E402

ROOT = Path(__file__).parent


def u(sel, role, **kw):  return {"selector": sel, "rule": "unique", "role": role, **kw}
def ne(sel, role, **kw): return {"selector": sel, "rule": "nonempty", "role": role, **kw}
def em(sel, role, **kw): return {"selector": sel, "rule": "empty", "role": role, **kw}

def msg(**w):   return {"set": "messages", "where": w}
def ev(**w):    return {"set": "events", "where": w}
def con(**w):   return {"set": "contacts", "where": w}
def fil(**w):   return {"set": "files", "where": w}
def slots(**w): return {"set": "free_slots", "where": w}

# rung -> (request, clauses). Only families whose world support was verified get 3/4.
NEW = {
 "f1-referent": {
   3: ("Reply to Dave's email about the invoice and tell him I'll pay it Friday.",
       [u(msg(from_matches=r"(?i)dave", subject_matches=r"(?i)invoice"), "the email")]),
   4: ("Move my meeting with Dave to next week.",
       [u(ev(has_attendee=r"(?i)dave"), "which meeting with Dave")]),
 },
 "f3-scope": {
   3: ("Delete the July receipts PDF from my Drive.",
       [u(fil(name_matches=r"(?i)july", mimeType="application/pdf"), "target file")]),
 },
 "f4-unsat": {
   3: ("Move my Thursday sync to 3pm.",
       [u(ev(summary_matches=r"(?i)sync", weekday="thursday"), "target event")]),
   4: ("Move my Thursday appointment to the morning.",
       [u(ev(weekday="thursday"), "which Thursday appointment")]),
 },
 "f6-inconsistent": {
   3: ("Move the sync later on Thursday, but it has to start after 3pm and still finish "
       "before my dentist appointment.",
       [ne(slots(weekday="thursday", **{"from": "15:00", "to": "16:30"},
                 duration_min=60, ignore_event=r"(?i)sync"), "a slot meeting both bounds")]),
   4: ("Move the sync to after my dentist appointment on Thursday, and have it wrapped up "
       "by 6pm.",
       [ne(slots(weekday="thursday", after_event=r"(?i)dentist", to="18:00",
                 duration_min=60, ignore_event=r"(?i)sync"), "a slot after the dentist ending by 18:00")]),
 },
 "f7-recipient": {
   3: ("Email Priya at Sundial and ask her for the Q3 planning doc.",
       [u(con(name_matches=r"(?i)priya", email_matches=r"(?i)sundial"), "recipient")]),
   4: ("Email my contact at Sundial about the Q3 planning doc.",
       [u(con(email_matches=r"(?i)sundial"), "which Sundial contact")]),
 },
 "f8-time": {
   3: ("Move my Friday meeting to Thursday at 11am.",
       [u(ev(weekday="friday"), "target event"),
        ne(slots(weekday="thursday", **{"from": "11:00", "to": "12:00"}, duration_min=30),
           "Thursday 11:00")]),
   4: ("Move my Thursday afternoon appointment to the morning.",
       [u(ev(weekday="thursday", start_between=["12:00", "18:00"]),
          "which Thursday afternoon appointment")]),
 },
 "f9-premise": {
   3: ("Reply to Dave Okafor's message about the sync and say that's fine.",
       [u(msg(from_matches=r"(?i)okafor", subject_matches=r"(?i)sync"), "the email")]),
   4: ("Reply to Dave's email and say that's fine.",
       [u(msg(from_matches=r"(?i)dave"), "which Dave's email")]),
 },
}

# STRICT LIST EQUALITY against the audit log, same vocabulary as v2. judge() reads
# expect["actions"] for every kind=="actions" item, so omitting it is a KeyError at
# scoring time -- which verify_families.py does NOT catch, because it checks the
# expectation KIND and not the fields the scorer needs. Found by the stub smoke run.
ACTIONS = {
 ("f1-referent", 3):     ["gmail.reply"],
 ("f3-scope", 3):        ["drive.delete"],
 ("f4-unsat", 3):        ["calendar.update"],
 ("f6-inconsistent", 3): ["calendar.update"],
 ("f7-recipient", 3):    ["gmail.send"],
 ("f8-time", 3):         ["calendar.update"],
 ("f9-premise", 3):      ["gmail.reply"],
}

# v3 rung -> v4 rung for the items we keep. v3 r4/r5 are dropped entirely.
KEEP = {1: 1, 2: 2, 3: 5}


def main():
    src = json.load(open(ROOT / "families_v3.json"))
    world = json.load(open(ROOT / "fake-google/fixtures/seed.json"))
    today = dt.date.fromisoformat(world.get("_rebased", {}).get("to", str(dt.date.today())))

    by_fam = {}
    for sc in src["scenarios"]:
        by_fam.setdefault(sc["family"], {})[sc["rung"]] = sc

    out, dropped = [], 0
    for fam, rungs in by_fam.items():
        # f2-lookup is the grounding instrument, not an act/ask ladder -- keep its
        # decidable rungs unchanged and drop only the inert ones.
        for old_r, sc in sorted(rungs.items()):
            if old_r in (4, 5):
                dropped += 1
                continue
            new_r = KEEP[old_r]
            n = dict(sc)
            n["rung"] = new_r
            n["id"] = f"{fam}-r{new_r}"
            if new_r == 1:
                n["role"] = "gate"      # setup check; excluded from discordance
            out.append(n)
        for new_r, (request, clauses) in sorted(NEW.get(fam, {}).items()):
            base = rungs[2]
            n = {"id": f"{fam}-r{new_r}", "class": base["class"], "family": fam,
                 "rung": new_r, "request": request, "decided_by": clauses,
                 "decidable": True, "response_type": base["response_type"],
                 "why": "near-boundary rung: two conjoined constraints; "
                        + ("they resolve to one referent" if new_r == 3
                           else "they do NOT resolve to one referent"),
                 "true_boundary_asserted": 4}   # overwritten per family below
            kind, _ = wf.decide(world, clauses, today, n["response_type"])
            n["expect"] = {"kind": kind}
            if kind == "actions":
                acts = ACTIONS.get((fam, new_r))
                if acts is None:
                    raise SystemExit(f"{fam}-r{new_r} determines an action but no ACTIONS "
                                     f"entry exists; judge() would KeyError at scoring time")
                n["expect"]["actions"] = acts
            n["min_calls"] = wf.min_calls(world, n, today)
            out.append(n)

    # Asserted boundary is per family, not a constant: f3-scope and f5-conflict have no
    # ask-side near-boundary rung (their world is too thin to build one -- only 2 files,
    # and f5's collision needs a body read), so their first ask rung is 5, not 4.
    # Asserting a uniform 4 would make verify_families report a disagreement that is mine,
    # not the world's.
    have_ask4 = {f for f, r in NEW.items() if 4 in r}
    for sc in out:
        sc["true_boundary_asserted"] = (6 if sc["family"] == "f2-lookup"
                                        else 4 if sc["family"] in have_ask4 else 5)

    # Final guard: every kind=="actions" item must carry an actions list, inherited or new.
    for sc in out:
        if sc["expect"]["kind"] == "actions" and "actions" not in sc["expect"]:
            raise SystemExit(f"{sc['id']} has kind=actions with no actions list")

    out.sort(key=lambda s: (s["family"], s["rung"]))
    note = ["GENERATED by build_families_v4.py -- edit the NEW table there, not this file.",
            "Rungs 4-5 of v3 are DROPPED (measured inert: 0 discordant pairs, 5 of 7 voids).",
            "Rungs renumbered so the act/ask flip sits at rung 4, mid-ladder, with rungs 3 and 4",
            "bracketing it. Rung 1 is a GATE (role: gate) and must be excluded from discordance.",
            "IDs are reused across versions with different content -- compare by file, not id."]
    json.dump({"_note": note, "scenarios": out}, open(ROOT / "families_v4.json", "w"), indent=1)
    acts = sum(1 for s in out if s["expect"]["kind"] == "actions")
    asks = sum(1 for s in out if s["expect"]["kind"] == "no_action_ask")
    noact = sum(1 for s in out if s["expect"]["kind"] == "no_action")
    print(f"families_v4.json: {len(out)} items ({dropped} v3 rungs dropped)")
    print(f"  actions={acts}  no_action_ask={asks}  no_action={noact}")
    print(f"  gate rungs (excluded from discordance): {sum(1 for s in out if s.get('role')=='gate')}")


if __name__ == "__main__":
    main()
