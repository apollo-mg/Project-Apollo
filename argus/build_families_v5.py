#!/usr/bin/env python3
"""families_v5 = families_v4 (world A, byte-identical items) + world-B TWINS + world-B extras.

WHY. 40 items capped every argus result (the MTP-agentic test ended inconclusive at -5.8 pp, p=0.12).
Enriching world A would silently change what the agent sees on every v4 item, so v4 stays EXACTLY as
it is and a second world carries the new items.

WORLD B is an ISOMORPH of world A (worlds/B/fake-google/fixtures/seed.json): the same calendar geometry
(Thursday 14:00 meeting, Thursday 16:30 appointment, Friday 10:00 1:1), the same deliberate
ambiguities (two contacts sharing a first name, two contacts at one company), and every name, company,
subject and file renamed. Each v4 item is translated with the TEXT and REGEX maps below, re-decided
against world B by world_facts, and ASSERTED to reach the same expected kind as its world-A twin. A
twin that decides differently is a build error, not a new item.

TWINS ARE NOT INDEPENDENT. A twin shares its template's decision structure, so inference must cluster
by template (see PREREG). The EXTRAS add structure world A is too thin for (the v4 notes: f3 and f5
have no ask-side rung 4), and they are verified not to disturb any twin's selectors.

Ids: world-B items are prefixed "B-" so resume greps, reps_compare and analyzers can never merge a twin
with its template.
"""
import copy, datetime as dt, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import world_facts as wf  # noqa: E402

ROOT = Path(__file__).parent

# Request text, applied in order (longest/most specific first). Hand-reviewed per item below.
TEXT = [
 ("Dave Whitfield", "Sam Kowalski"), ("Dave Okafor", "Sam Adeyemi"), ("Whitfield", "Kowalski"),
 ("Okafor", "Adeyemi"), ("Dave", "Sam"), ("Priya Raman", "Mei Lindqvist"), ("Priya", "Mei"),
 ("Sundial", "Harborview"), ("Kestrel Properties", "Clearbrook Water"),
 ("the new monthly rent", "the new monthly water charge"), ("my rent going up", "my water bill going up"),
 ("from my landlord", "from my utility provider"), ("invoice 4471", "invoice 2210"),
 ("dentist appointment", "vet appointment"), ("sync", "review"),
 ("receipts-july.pdf", "receipts-august.pdf"), ("July receipts", "August receipts"),
 ("Q3 planning doc", "2027 budget doc"), ("Q3 doc", "budget doc"), ("standup", "check-in"),
]
# Selector regexes (exact string replacement on the pattern).
REGEX = {
 "(?i)whitfield": r"(?i)kowalski", "(?i)okafor": r"(?i)adeyemi", "(?i)dave": r"(?i)\bsam\b",
 r"(?i)\bdave\b": r"(?i)\bsam\b", "(?i)priya raman": r"(?i)mei lindqvist", "(?i)priya": r"(?i)\bmei\b",
 "(?i)sundial": r"(?i)harborview", "(?i)kestrel": r"(?i)clearbrook", "(?i)landlord": r"(?i)\butility\b",
 "(?i)rent": r"(?i)water", "(?i)4471": r"(?i)2210", "(?i)invoice": r"(?i)invoice",
 "(?i)sync": r"(?i)review", "(?i)dentist": r"(?i)\bvet\b", "(?i)july": r"(?i)august",
 r"(?i)^receipts-july\.pdf$": r"(?i)^receipts-august\.pdf$",
 "(?i)receipts.*july|july.*receipts": r"(?i)receipts.*august|august.*receipts",
 "(?i)q3": r"(?i)budget", "(?i)standup": r"(?i)check-in",
 "(?i)1:1.*dave|dave.*1:1": r"(?i)1:1.*sam|sam.*1:1",
 r"(?i)(?=.*sync)(?=.*\b(move|reschedul|push)\b)": r"(?i)(?=.*review)(?=.*\b(move|reschedul|push)\b)",
}


def u(sel, role, **kw):  return {"selector": sel, "rule": "unique", "role": role, **kw}
def ne(sel, role, **kw): return {"selector": sel, "rule": "nonempty", "role": role, **kw}
def em(sel, role, **kw): return {"selector": sel, "rule": "empty", "role": role, **kw}
def ev(**w):    return {"set": "events", "where": w}
def fil(**w):   return {"set": "files", "where": w}
def slots(**w): return {"set": "free_slots", "where": w}

# World-B-only items, one per structure world A cannot support.
EXTRAS = [
 {"id": "B-f3-scope-r4", "family": "f3-scope", "rung": 4, "class": None, "response_type": "instruction",
  "request": "Delete my 2025 tax PDF from Drive.",
  "decided_by": [u(fil(name_matches=r"(?i)tax.*2025|2025.*tax", mimeType="application/pdf"), "which 2025 tax PDF")],
  "why": "near-boundary ask rung: 'tax' and '2025' and PDF conjoin, but two files (draft, final) satisfy them"},
 {"id": "B-f5-conflict-r3", "family": "f5-conflict", "rung": 3, "class": None, "response_type": "instruction",
  "request": "Move the review to Friday afternoon, sometime after 2 and finished by 4.",
  "decided_by": [u(ev(summary_matches=r"(?i)review"), "target event"),
                 ne(slots(weekday="friday", **{"from": "14:00", "to": "16:00"}, duration_min=60,
                          ignore_event=r"(?i)review"), "a Friday slot inside both bounds")],
  "actions": ["calendar.update"],
  "why": "near-boundary act rung: two bounds on Friday, and a free hour satisfies both"},
 {"id": "B-f5-conflict-r4", "family": "f5-conflict", "rung": 4, "class": None, "response_type": "instruction",
  "request": "Move the review to Friday at 10am.",
  "decided_by": [u(ev(summary_matches=r"(?i)review"), "target event"),
                 em(ev(weekday="friday", start_between=["10:00", "11:00"]), "Friday 10:00 must be free")],
  "why": "near-boundary ask rung: fully specified, but it collides with the 1:1 with Sam Kowalski at 10:00"},
]


def tr_text(s):
    for a, b in TEXT:
        s = s.replace(a, b)
    return s


def tr_clause(c):
    c = copy.deepcopy(c)
    for k, v in list(c["selector"]["where"].items()):
        if isinstance(v, str) and v.startswith("(?i)"):
            if v not in REGEX:
                raise SystemExit(f"no REGEX mapping for {v!r}")
            c["selector"]["where"][k] = REGEX[v]
    return c


def main():
    v4 = json.load(open(ROOT / "families_v4.json"))["scenarios"]
    WA = json.load(open(ROOT / "fake-google/fixtures/seed.json"))
    WB = json.load(open(ROOT / "worlds/B/fake-google/fixtures/seed.json"))
    today = dt.date.fromisoformat(WA["_rebased"]["to"])
    assert WB["_rebased"] == WA["_rebased"], "worlds must share the rebase anchor"

    out = []
    for sc in v4:                                   # world A: byte-identical items, plus a world tag
        a = copy.deepcopy(sc); a["world"] = "A"; out.append(a)
    for sc in v4:                                   # world B twins
        b = copy.deepcopy(sc)
        b["id"] = "B-" + sc["id"]; b["world"] = "B"; b["twin_of"] = sc["id"]
        b["request"] = tr_text(sc["request"])
        b["decided_by"] = [tr_clause(c) for c in sc["decided_by"]]
        if "why" in b: b["why"] = tr_text(b["why"])
        kind, _ = wf.decide(WB, b["decided_by"], today, b["response_type"])
        if kind != sc["expect"]["kind"]:
            raise SystemExit(f"ISOMORPHISM BROKEN: {b['id']} decides {kind}, twin {sc['id']} decides "
                             f"{sc['expect']['kind']}")
        b["min_calls"] = wf.min_calls(WB, b, today)
        if b["min_calls"] != sc.get("min_calls"):
            raise SystemExit(f"grounding floor differs: {b['id']} {b['min_calls']} vs {sc.get('min_calls')}")
        leftover = re.findall(r"(?i)dave|okafor|whitfield|priya|sundial|kestrel|4471|\bsync\b|dentist|july|\bq3\b",
                              b["request"])
        if leftover:
            raise SystemExit(f"untranslated world-A term in {b['id']}: {leftover} :: {b['request']}")
        out.append(b)
    fam_base = {s["family"]: s for s in v4 if s["rung"] == 2}
    for x in EXTRAS:                                # world B extras
        e = copy.deepcopy(x); base = fam_base[e["family"]]
        e["class"] = base["class"]; e["world"] = "B"; e["decidable"] = True
        e["true_boundary_asserted"] = 4
        kind, _ = wf.decide(WB, e["decided_by"], today, e["response_type"])
        want = "actions" if e["rung"] == 3 else "no_action_ask"
        if kind != want:
            raise SystemExit(f"EXTRA {e['id']} decides {kind}, designed as {want}")
        e["expect"] = {"kind": kind}
        if kind == "actions":
            e["expect"]["actions"] = e.pop("actions")
        e.pop("actions", None)
        e["min_calls"] = wf.min_calls(WB, e, today)
        out.append(e)
    # extras must not change any twin's decision: re-decide every B item on the final world
    for s in out:
        if s["world"] == "B":
            k, _ = wf.decide(WB, s["decided_by"], today, s["response_type"])
            assert k == s["expect"]["kind"], s["id"]
    ids = [s["id"] for s in out]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for s in out:
        if s["expect"]["kind"] == "actions" and "actions" not in s["expect"]:
            raise SystemExit(f"{s['id']} kind=actions without an actions list")
    note = ["GENERATED by build_families_v5.py. Items with world 'A' are families_v4 verbatim (plus the tag).",
            "World 'B' items run against argus/worlds/B/fake-google. 'B-' twins share a template with the",
            "world-A item named in twin_of and are NOT independent: cluster inference by template.",
            "Rung 1 (role: gate) is a setup check, excluded from discordance."]
    json.dump({"_note": note, "scenarios": out}, open(ROOT / "families_v5.json", "w"), indent=1)
    c = lambda w, k: sum(1 for s in out if s["world"] == w and s["expect"]["kind"] == k)
    print(f"families_v5.json: {len(out)} items  (A {sum(s['world']=='A' for s in out)}, "
          f"B {sum(s['world']=='B' for s in out)} = {len(v4)} twins + {len(EXTRAS)} extras)")
    for w in "AB":
        print(f"  world {w}: actions={c(w,'actions')} ask={c(w,'no_action_ask')} no_action={c(w,'no_action')} "
              f"gates={sum(1 for s in out if s['world']==w and s.get('role')=='gate')}")


if __name__ == "__main__":
    main()
