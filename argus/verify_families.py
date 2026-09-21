#!/usr/bin/env python3
"""Recompute every item's expectation from the fixture world and report disagreements.

Run this after ANY seed edit, any rebase_seed.py, and before any pilot.  The
corpus's expectations are not stored facts -- they are consequences of the world,
and this is what makes them consequences rather than claims.

Exit 0 clean, 2 on any disagreement, 1 on a usage error.
"""
import argparse
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import world_facts as wf  # noqa: E402


def derive_boundary(items, computed):
    """Lowest rung that does NOT determine an action.

    None when every decidable rung determines one -- the f2 case, where the
    ladder never flips to ask and the measured quantity is something else.
    Rungs that are not world-decidable cannot participate: a boundary derived
    across a gap would be reported as fact while resting on an asserted rung.
    """
    asks = [s["rung"] for s in items if s["decidable"] and computed[s["id"]][0] == "no_action_ask"]
    return min(asks) if asks else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default=str(Path(__file__).parent / "families_v3.json"))
    ap.add_argument("--world", default=str(Path(__file__).parent / "fake-google/fixtures/seed.json"))
    ap.add_argument("--today", help="YYYY-MM-DD; default is the real today, as the driver uses")
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    world = json.load(open(a.world))
    scs = json.load(open(a.families))["scenarios"]

    print(f"world  {a.world}")
    print(f"today  {today} ({wf.WEEKDAYS[today.weekday()]})"
          + (f"   world rebased to {world['_rebased']['to']}" if "_rebased" in world else ""))
    print(f"items  {len(scs)}\n")

    computed, kind_bad, undecidable, ground_bad = {}, [], [], []
    for sc in scs:
        ground_bad += [(sc["id"], m) for m in wf.check_grounding(world, sc)]
        # judge() reads expect["actions"] for every kind=="actions" item. Checking the
        # expectation KIND alone let a corpus through that KeyError'd at scoring time.
        if sc["expect"]["kind"] == "actions" and not sc["expect"].get("actions"):
            ground_bad.append((sc["id"], "kind=actions but expect.actions is missing/empty "
                                         "-- judge() would raise at scoring time"))
        if not sc["decidable"]:
            undecidable.append(sc)
            computed[sc["id"]] = (None, [sc["not_decidable_because"]])
            continue
        kind, notes = wf.decide(world, sc["decided_by"], today, sc["response_type"])
        computed[sc["id"]] = (kind, notes)
        if kind != sc["expect"]["kind"]:
            kind_bad.append((sc, kind, notes))

    print("== per-item expectation ==")
    for sc in scs:
        kind, notes = computed[sc["id"]]
        if kind is None:
            print(f"  {sc['id']:22} --  NOT DECIDABLE")
            continue
        mark = "ok " if kind == sc["expect"]["kind"] else "BAD"
        print(f"  {sc['id']:22} {mark} computed={kind:14} stored={sc['expect']['kind']}")
        for n in notes:
            print(f"  {'':22}     {n}")

    print("\n== retrieval depth (min_calls: the floor below which an answer is ungrounded) ==")
    weak = []
    for sc in scs:
        mc = wf.min_calls(world, sc, today)
        g = "".join(f" {x['set']}/{x['id']}.{x['field']}" for x in sc.get("grounded_in", []))
        if sc.get("min_calls") not in (None, mc):
            ground_bad.append((sc["id"], f"baked min_calls={sc['min_calls']} but recomputes to {mc}"))
        if mc >= 2:
            print(f"  {sc['id']:22} min_calls={mc}{'   answer in:' + g if g else ''}")
        # judge() passes no_action/no_action_ask at ncalls>=1. An item needing more
        # than one read can therefore pass while never having seen its own answer.
        if mc >= 2 and sc["expect"]["kind"] in ("no_action", "no_action_ask"):
            weak.append((sc["id"], mc, sc["expect"]["kind"]))
    if weak:
        print("\n  THRESHOLD TOO WEAK -- judge() accepts ncalls>=1 for these:")
        for sid, mc, kind in weak:
            print(f"    {sid:22} needs {mc} reads, scored {kind} at 1")

    # A generated corpus is matched PAIRS, not a rung ladder, so it carries no
    # asserted boundary to check against. Skip rather than invent one.
    laddered = [s for s in scs if "true_boundary_asserted" in s]
    boundary_bad = []
    if not laddered:
        print("\n== true_boundary: n/a (no laddered items; this is a paired corpus) ==")
        print("\n== matched pairs ==")
        pairs = {}
        for s in scs:
            pairs.setdefault(s.get("template", "?"), {}).setdefault(s.get("arm", "?"), []).append(s)
        for tpl, arms in sorted(pairs.items()):
            det = len(arms.get("determined", []))
            ask = len(arms.get("ask", []))
            flag = "" if det == ask else "   UNMATCHED -- a pair needs both arms"
            if det != ask:
                boundary_bad.append((tpl, det, ask, []))
            print(f"  {tpl:18} determined={det:>3} ask={ask:>3}{flag}")
    else:
        print("\n== true_boundary: derived vs asserted ==")
    for fam, group in itertools.groupby(laddered, key=lambda s: s["family"]):
        items = list(group)
        got = derive_boundary(items, computed)
        want = items[0]["true_boundary_asserted"]
        gaps = [s["rung"] for s in items if not s["decidable"]]
        # asserted 6 is v2's "never flips to ask", which derives as None
        agree = (got == want) or (got is None and want == 6)
        # A boundary is only sound if every rung BELOW it was actually decided.
        # An undecidable rung under the derived minimum could be the real flip
        # point, and the number would be reported as computed while resting on
        # an assertion -- exactly what this file exists to prevent.
        unsound = [r for r in gaps if got is not None and r < got]
        if not agree or unsound:
            boundary_bad.append((fam, got, want, unsound))
        print(f"  {fam:16} derived={str(got):5} asserted={want}  "
              f"{'ok' if agree and not unsound else 'DISAGREES' if not agree else 'UNSOUND'}"
              + (f"   (rungs {gaps} not decidable)" if gaps else "")
              + (f"   <- rung(s) {unsound} below the boundary are asserted, not decided" if unsound else ""))

    print(f"\n== summary ==")
    print(f"  decidable          {sum(1 for s in scs if s['decidable'])}/{len(scs)}")
    print(f"  expectation agrees {sum(1 for s in scs if s['decidable']) - len(kind_bad)}"
          f"/{sum(1 for s in scs if s['decidable'])}")
    if laddered:
        nfam = len({s["family"] for s in laddered})
        print(f"  boundary agrees    {nfam - len(boundary_bad)}/{nfam}")

    if ground_bad:
        print("\nUNGROUNDABLE -- the answer is not where the corpus says it is:")
        for sid, m in ground_bad:
            print(f"  {sid}: {m}")

    if kind_bad or boundary_bad or ground_bad:
        print("\nDISAGREEMENTS -- the world does not support what the corpus claims:")
        for sc, kind, notes in kind_bad:
            print(f"  {sc['id']}: stored {sc['expect']['kind']}, world says {kind}")
            for n in notes:
                print(f"      {n}")
            print(f"      v2's reason was: {sc['why']}")
        for fam, got, want, unsound in boundary_bad:
            print(f"  {fam}: true_boundary asserted {want}, derived {got}"
                  + (f"; rung(s) {unsound} below it are not decidable" if unsound else ""))
        return 2
    print("\nclean -- every decidable expectation and boundary follows from the world")
    return 0


if __name__ == "__main__":
    sys.exit(main())
