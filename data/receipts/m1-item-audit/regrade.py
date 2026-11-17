#!/usr/bin/env python3
"""M1 item audit, step 3: what the proposed key changes would do to stored results. Read-only; M1-v1 stays frozen.

(a) Accent folding: real-item answers graded WRONG that equal a gold alias once accents are folded (Fes = Fez).
(b) The proposed v2 key (AUDIT_M1_ITEMS.md): added answers for ambiguous and mis-keyed items, the accent fold, and
    the training-cutoff item dropped. Reports the change in easy and hard accuracy per primary arm, and in the paired
    hard-accuracy difference for the published base-versus-variant pairs.
Usage: regrade.py"""
import json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(HERE.parent / "viability"))
from run_fixture import bare  # noqa: E402

REG = json.load(open(HERE.parents[1] / "scorecard" / "registry.json"))
ITEMS = {json.loads(l)["id"]: json.loads(l) for l in open(QA / "corpus" / "M1.jsonl")}
EXTRA = {"M1-H-cap-043": ["Fès"], "M1-E-uni-030": ["1865"], "M1-E-nov-011": ["1849"], "M1-E-uni-038": ["1932"], "M1-H-cap-055": ["Čučer-Sandevo"],
         "M1-H-nov-084": ["1853"], "M1-H-uni-116": ["2005"]}            # the audit's proposed added answers
DROP = {"M1-H-nov-086"}                                                   # tests the training cutoff, not recall
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
PAIRS = [("Q36B2", "SGQ6", "Sage, matched Q6_K"), ("S25G", "S26G", "Spark 2.5 vs 2.6"), ("C.A", "ARE", "Arete"),
         ("ABL_S6", "ABL_U6", "abliteration"), ("C.A", "QWC", "Qwopus Coder")]


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", bare(s)) if not unicodedata.combining(c))


def names(it):
    """The key's names, plus each name without a trailing ', <country>' ('Fes, Morocco' -> 'Fes'): a v2 rule."""
    ns = it.get("gold_aliases") or [it["gold"]]
    return ns + [n.split(",")[0] for n in ns if "," in n]


def v2_correct(it, got, g):
    if g == "CORRECT":
        return True
    if g != "WRONG":
        return False
    accepted = names(it) + EXTRA.get(it["id"], [])
    if any(fold(got) == fold(a) for a in accepted):
        return True
    if it["template"] in ("novel", "university"):                        # the lenient rule: exactly one year named
        ys = set(YEAR.findall(got or ""))
        return len(ys) == 1 and ys <= set(it.get("gold_years_lenient", [])) | set(EXTRA.get(it["id"], []))
    return False


def rows(arm):
    p = QA / "raw" / f"main_{arm}.jsonl"
    return [r for r in map(json.loads, open(p)) if "id" in r] if p.exists() else []


def acc(rs, group, v2):
    sel = [r for r in rs if ITEMS[r["id"]]["arm"] == group and not (v2 and r["id"] in DROP)]
    ok = [(v2_correct(ITEMS[r["id"]], r.get("got") or "", r.get("grade_lenient") or r.get("grade")) if v2
           else (r.get("grade_lenient") or r.get("grade")) == "CORRECT") for r in sel]
    return sum(ok) / len(ok) if ok else float("nan")


def main():
    flips, arms_hit, n_rows = Counter(), set(), 0
    for arm in REG["m1_arms"]:
        for r in rows(arm):
            it = ITEMS[r["id"]]
            if it["arm"] == "U" or (r.get("grade_lenient") or r.get("grade")) != "WRONG":
                continue
            n_rows += 1
            if any(fold(r.get("got") or "") == fold(a) for a in names(it)):
                flips[r["id"]] += 1; arms_hit.add(arm)
    print(f"(a) accent fold plus the country-suffix rule: {sum(flips.values())} of {n_rows} WRONG real-item answers across {len(arms_hit)} arms become correct; "
          + ", ".join(f"{i} x{n}" for i, n in flips.most_common()))
    prim = [(v["model"], a) for a, v in REG["m1_arms"].items() if v.get("primary") and v.get("thinking") == "off" and rows(a)]
    seen, dE, dH = set(), [], []
    print("\n(b) proposed v2 key, primary thinking-off arms: change in accuracy (v2 - v1)")
    for m, a in prim:
        if m in seen:
            continue
        seen.add(m); rs = rows(a)
        e, h = acc(rs, "E", True) - acc(rs, "E", False), acc(rs, "H", True) - acc(rs, "H", False)
        dE.append(e); dH.append(h)
    print(f"   {len(dE)} models: easy +{min(dE):.3f} to +{max(dE):.3f} (mean +{sum(dE) / len(dE):.3f}); "
          f"hard {min(dH):+.3f} to {max(dH):+.3f} (mean {sum(dH) / len(dH):+.3f})")
    print("\n   published pairs, hard accuracy variant - base: v1 -> v2")
    for b, v, name in PAIRS:
        rb, rv = rows(b), rows(v)
        if not rb or not rv:
            print(f"   {name}: arms {b}/{v} not found"); continue
        d1 = acc(rv, "H", False) - acc(rb, "H", False); d2 = acc(rv, "H", True) - acc(rb, "H", True)
        print(f"   {name:22} {d1:+.3f} -> {d2:+.3f}")


if __name__ == "__main__":
    main()
