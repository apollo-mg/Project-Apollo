#!/usr/bin/env python3
"""Refuse to compare two fixture runs that were not measured the same way.

Written 2026-09-12, after an hour of archaeology established that the `card_xhigh_rep*` baseline
(11/24 failures) ran at `-c 8192` while the runs being compared against it ran at `-c 16384` —
so five of its eleven failures were a retry-budget artefact, not a model property. Nothing checked;
two numbers were read off two receipts and subtracted.

Everything here is recovered from what the rows already record, so it works on datasets written
before the runner learned to log its own configuration:

  implied n_ctx   the runner sets the escalated retry to min(n_predict*2, n_ctx - 1024), so a
                  second attempt of N implies n_ctx = N + 1024 unless it was capped at 2x
  n_predict       first element of the first attempt
  sampling        recorded per row
  items           the id set actually present
  effort/model    only if the row carries them (added to the runner 2026-09-12)

Exit status is 1 when anything differs, so it can gate a scoring script.

Usage:
  compare_runs.py 'card_xhigh_rep*.jsonl' 'overthink/armA_rep*.jsonl'
  compare_runs.py --quiet A.jsonl B.jsonl && ./score.py ...
"""
import argparse, glob, json, sys
from collections import Counter


def load(pattern):
    rows = []
    for f in sorted(glob.glob(pattern)):
        with open(f) as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def implied_n_ctx(rows):
    """Recover the server context from escalated-retry budgets. Returns a set of candidates."""
    out = set()
    for r in rows:
        a = r.get("attempts") or []
        if len(a) >= 2:
            first, second = a[0][0], a[1][0]
            # second = min(first*2, n_ctx - 1024). If it is below the 2x ceiling, it WAS the
            # headroom and n_ctx is recoverable exactly. If it equals 2x, n_ctx is only bounded.
            out.add(second + 1024 if second < first * 2 else f">={second + 1024}")
    return out


def profile(rows):
    p = {}
    p["rows"] = len(rows)
    p["sampling"] = sorted({str(r.get("sampling")) for r in rows})
    p["n_predict"] = sorted({(r.get("attempts") or [[None]])[0][0] for r in rows if r.get("attempts")})
    nc = implied_n_ctx(rows)
    p["implied n_ctx"] = sorted(map(str, nc)) if nc else ["(no escalated retry in this data)"]
    p["items"] = sorted({r.get("id") for r in rows if r.get("id")})
    p["arms"] = sorted({str(r.get("arm")) for r in rows})
    for opt in ("effort", "model", "host", "n_ctx", "arm_label", "budget_tokens"):
        vals = sorted({str(r[opt]) for r in rows if opt in r})
        if vals:
            p[opt] = vals
    return p


COMPARE = ["sampling", "n_predict", "arms", "effort", "model", "n_ctx", "budget_tokens"]


def ctx_verdict(va, vb):
    """Compare implied-context evidence. Returns (status, note).

    A value is either an exact int, a lower bound ">=N", or absent because the run never escalated.
    Unknown is NOT a mismatch -- it is unverifiable, which the caller must be told without being
    blocked. A checker that cries wolf gets ignored, and then it protects nothing.
    """
    def parse(vals):
        ex, lo = set(), set()
        for v in vals or []:
            v = str(v)
            if v.startswith(">="): lo.add(int(v[2:]))
            elif v.isdigit(): ex.add(int(v))
        return ex, lo
    ea, la = parse(va)
    eb, lb = parse(vb)
    if not (ea or la) or not (eb or lb):
        return "unknown", "no escalated retry on one side; context not recoverable from the data"
    if ea and eb:
        return ("same", f"both {ea.pop()}") if ea == eb else ("differ", f"{sorted(ea)} vs {sorted(eb)}")
    # one side is only bounded: compatible if the exact value satisfies the bound
    if ea and lb:
        e, b = min(ea), max(lb)
        return ("same", f"{e} satisfies >={b}") if e >= b else ("differ", f"{e} < required >={b}")
    if eb and la:
        e, b = min(eb), max(la)
        return ("same", f"{e} satisfies >={b}") if e >= b else ("differ", f"{e} < required >={b}")
    return "unknown", f"both only bounded: >={max(la)} vs >={max(lb)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--quiet", action="store_true", help="print only mismatches")
    ap.add_argument("--allow", default="", help="comma-separated fields to ignore (declared differences)")
    args = ap.parse_args()

    A, B = load(args.a), load(args.b)
    if not A or not B:
        sys.exit(f"no rows: A={len(A)} B={len(B)}")
    pa, pb = profile(A), profile(B)
    allow = {x.strip() for x in args.allow.split(",") if x.strip()}

    bad = []
    for k in COMPARE:
        va, vb = pa.get(k), pb.get(k)
        if va is None and vb is None:
            continue
        if va != vb:
            (bad if k not in allow else []).append(k)
            mark = "~" if k in allow else "x"
            print(f"  {mark} {k:16s} A={va}  B={vb}" + ("   (declared)" if k in allow else ""))
        elif not args.quiet:
            print(f"  . {k:16s} {va}")

    st, note = ctx_verdict(pa.get("implied n_ctx"), pb.get("implied n_ctx"))
    if st == "differ":
        bad.append("implied n_ctx")
        print(f"  x {'implied n_ctx':16s} {note}")
    elif st == "unknown":
        print(f"  ? {'implied n_ctx':16s} UNVERIFIABLE — {note}")
    elif not args.quiet:
        print(f"  . {'implied n_ctx':16s} {note}")

    ia, ib = set(pa["items"]), set(pb["items"])
    if ia != ib:
        bad.append("items")
        print(f"  x {'items':16s} only in A: {sorted(ia - ib)}  only in B: {sorted(ib - ia)}")
    elif not args.quiet:
        print(f"  . {'items':16s} identical, {len(ia)} ids")

    if not args.quiet:
        print(f"  . {'rows':16s} A={pa['rows']} B={pb['rows']}")

    if bad:
        print(f"\nREFUSING — {len(bad)} config mismatch(es): {', '.join(bad)}")
        print("These runs are not apples-to-apples. Match them, or pass --allow to declare the")
        print("difference explicitly and say so in the receipt.")
        return 1
    print("\nComparable on every recoverable field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
