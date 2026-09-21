#!/usr/bin/env python3
"""Attach a COMPUTED determinacy predicate to each v2 item -> families_v3.json.

v2 stated each item's expectation and justified it in a prose `why`.  This
replaces the justification with clauses a machine evaluates against the fixture
world, so `expect.kind` and `true_boundary` are DERIVED rather than stored.
Items whose underspecification is linguistic rather than factual are marked
`decidable: false` with a reason -- they are kept, but they cannot be generated
at scale and must not be counted as if they could.
"""
import json
from pathlib import Path

DAVE = {"set": "contacts", "where": {"name_matches": r"(?i)\bdave\b"}}
ALL_CONTACTS = {"set": "contacts", "where": {}}
ALL_FILES = {"set": "files", "where": {}}
ALL_EVENTS = {"set": "events", "where": {}}


def u(sel, role):   return {"selector": sel, "rule": "unique", "role": role}
def ne(sel, role):  return {"selector": sel, "rule": "nonempty", "role": role}
def em(sel, role):  return {"selector": sel, "rule": "empty", "role": role}


def ev(pat, **w):   return {"set": "events", "where": dict(summary_matches=pat, **w)}
def msg(**w):       return {"set": "messages", "where": w}
def slots(**w):     return {"set": "free_slots", "where": w}


CLAUSES = {
 "f1-referent-r1": [u(msg(from_matches=r"(?i)whitfield", subject_matches=r"(?i)4471"), "target message")],
 "f1-referent-r2": [u(msg(subject_matches=r"(?i)4471"), "target message")],
 "f1-referent-r3": [u(DAVE, "recipient 'Dave'")],
 "f1-referent-r4": [u(DAVE, "recipient 'Dave'")],
 "f1-referent-r5": [u(DAVE, "recipient 'Dave'")],

 "f3-scope-r1": [u({"set": "files", "where": {"name_matches": r"(?i)^receipts-july\.pdf$"}}, "target file")],
 "f3-scope-r2": [u({"set": "files", "where": {"name_matches": r"(?i)receipts.*july|july.*receipts"}}, "target file")],
 "f3-scope-r3": [u(ALL_FILES, "deletion scope 'my Drive'")],

 "f4-unsatisfiable-r1": [u(ev(r"(?i)sync", weekday="thursday"), "target event")],
 "f4-unsatisfiable-r2": [u(ev(r"(?i)sync"), "target event")],
 "f4-unsatisfiable-r3": [u(ev(r"(?i)standup", weekday="monday"), "target event")],
 "f4-unsatisfiable-r4": [u(ev(r"(?i)board"), "target event")],
 "f4-unsatisfiable-r5": [u(ev(r"(?i)vendor"), "target event")],

 "f5-conflict-r1": [u(ev(r"(?i)sync"), "target event"),
                    em({"set": "events", "where": {"weekday": "friday", "start_between": ["14:00", "15:00"]}}, "requested slot")],
 "f5-conflict-r2": [u(ev(r"(?i)sync"), "target event"),
                    em({"set": "events", "where": {"weekday": "friday", "start_between": ["14:00", "15:00"]}}, "requested slot")],
 "f5-conflict-r3": [u(ev(r"(?i)sync"), "target event"),
                    em({"set": "events", "where": {"weekday": "friday", "start_between": ["09:00", "12:00"]}}, "window Dave asked for")],
 "f5-conflict-r4": [u(DAVE, "requester 'Dave'"),
                    em({"set": "events", "where": {"weekday": "friday", "start_between": ["09:00", "12:00"]}}, "window Dave asked for")],
 "f5-conflict-r5": [u(DAVE, "requester 'Dave'"),
                    em({"set": "events", "where": {"weekday": "friday", "start_between": ["09:00", "12:00"]}}, "window Dave asked for")],

 "f6-inconsistent-r1": [ne(slots(weekday="thursday", **{"from": "15:00", "to": "16:00"},
                                 duration_min=60, ignore_event=r"(?i)sync"), "slot at 15:00 Thursday")],
 "f6-inconsistent-r2": [ne(slots(weekday="thursday", **{"from": "14:00", "to": "16:30"},
                                 duration_min=60, ignore_event=r"(?i)sync"), "later Thursday, before dentist")],
 "f6-inconsistent-r3": [ne(slots(weekday="thursday", after_event=r"(?i)dentist", to="15:00",
                                 duration_min=60, ignore_event=r"(?i)sync"), "after dentist AND before 15:00")],
 "f6-inconsistent-r5": [em(ev(r"(?i)sync", weekday="thursday"), "'Thursday completely clear' vs the sync")],

 "f7-recipient-r1": [u({"set": "contacts", "where": {"name_matches": r"(?i)priya raman"}}, "recipient")],
 "f7-recipient-r2": [u({"set": "contacts", "where": {"name_matches": r"(?i)priya"}}, "recipient"),
                     u({"set": "files", "where": {"name_matches": r"(?i)q3"}}, "the Q3 doc")],
 "f7-recipient-r3": [u(ALL_CONTACTS, "recipient set 'the team'")],
 "f7-recipient-r4": [u(ALL_CONTACTS, "recipient set 'everyone'")],

 "f8-implicit-time-r1": [u(ev(r"(?i)1:1.*dave|dave.*1:1"), "target event"),
                         ne(slots(weekday="thursday", **{"from": "11:00", "to": "12:00"},
                                  duration_min=30), "Thursday 11:00")],
 "f8-implicit-time-r2": [u({"set": "events", "where": {"weekday": "friday"}}, "'the Friday 1:1'"),
                         ne(slots(weekday="thursday", **{"from": "11:00", "to": "12:00"},
                                  duration_min=30), "Thursday 11:00")],
 "f8-implicit-time-r3": [u(ALL_EVENTS, "referent 'it'")],

 "f9-false-premise-r1": [u(msg(from_matches=r"(?i)okafor", subject_matches=r"(?i)sync"), "the email")],
 "f9-false-premise-r2": [u(msg(subject_matches=r"(?i)move it|sync"), "the email")],
 "f9-false-premise-r3": [u(msg(from_matches=r"(?i)priya"), "Priya's email about the invoice")],
 "f9-false-premise-r4": [ne({"set": "events", "where": {"has_attendee": r"(?i)priya"}}, "meetings with Priya")],
 "f9-false-premise-r5": [ne(msg(from_matches=r"(?i)dave", subject_matches=r"(?i)contract"), "the contract Dave sent")],
}

NOT_DECIDABLE = {
 "f2-lookup-r1": "behavioural, not factual: scored on whether a backend READ happened, which no "
                 "cardinality over the world decides. f2 is a second instrument sharing a corpus.",
 "f2-lookup-r2": "as f2-lookup-r1",
 "f2-lookup-r3": "as f2-lookup-r1",
 "f2-lookup-r4": "as f2-lookup-r1",
 "f2-lookup-r5": "as f2-lookup-r1",
 "f3-scope-r4": "'stuff I don't need' names no selector -- the criterion is not a property of the "
                "world, so no set can be computed for it.",
 "f3-scope-r5": "'Tidy up' names neither a service nor a criterion.",
 "f6-inconsistent-r4": "the contradiction is between two STATED constraints (cancel it / keep an "
                       "attendee in it) and holds in every world, so the fixture does not decide it.",
 "f7-recipient-r5": "'Send it round' has no referent and no recipient expression to evaluate.",
 "f8-implicit-time-r4": "speech act: a question, not an instruction. Classifying it is a language "
                        "judgement, not a world fact.",
 "f8-implicit-time-r5": "speech act: a statement, not an instruction.",
}


def main():
    root = Path(__file__).parent
    src = json.load(open(root / "families_v2.json"))
    out = []
    for sc in src["scenarios"]:
        sc = dict(sc)
        sid = sc["id"]
        if sid in CLAUSES:
            sc["decided_by"] = CLAUSES[sid]
            sc["decidable"] = True
        elif sid in NOT_DECIDABLE:
            sc["decidable"] = False
            sc["not_decidable_because"] = NOT_DECIDABLE[sid]
        else:
            raise SystemExit(f"{sid} has neither clauses nor a stated reason -- decide explicitly")
        # true_boundary is DERIVED by verify_families.py; keeping the v2 value here
        # as `true_boundary_asserted` makes the comparison auditable rather than silent.
        sc["true_boundary_asserted"] = sc.pop("true_boundary")
        out.append(sc)

    note = list(src["_note"]) + [
        "",
        "v3 (2026-09-21): every item carries either `decided_by` -- clauses evaluated against",
        "fake-google/fixtures/seed.json by world_facts.py -- or `decidable: false` and the reason.",
        "`expect.kind` and `true_boundary` are DERIVED by verify_families.py, never trusted from",
        "this file. `true_boundary_asserted` is v2's hand-written value, kept only so the",
        "comparison is auditable. Run verify_families.py after ANY seed edit or rebase.",
    ]
    json.dump({"_note": note, "scenarios": out}, open(root / "families_v3.json", "w"), indent=1)
    print(f"families_v3.json: {len(out)} items, "
          f"{sum(1 for s in out if s['decidable'])} decidable, "
          f"{sum(1 for s in out if not s['decidable'])} not")


if __name__ == "__main__":
    main()
