#!/usr/bin/env python3
"""Emit a VERDICT, not a dataset.

Written because reading benchmark output into an LLM context is the single
biggest token cost in this campaign, and almost all of it is waste. A 7-arm run
printed 168 lines of per-prompt detail when the decision needed 7 numbers.
Tokens are the binding constraint on this project (not compute, not disk), so
the harnesses must summarise before a model ever sees them.

Rules this follows, each one bought with a failure from FAILURE_MODES.md:

  AFM-7  assert the expected arm count and SAY SO when short, rather than
         silently summarising whatever happened to be on disk.
  AFM-6  report rep-to-rep stability next to every number, because a value
         whose replication was never checked is not a result.
  AFM-4  never print an aggregate without the per-subgroup spread, since
         aggregates can match while subgroups differ with consistent signs.
  AFM-1  print the within-arm spread beside the between-arm difference so the
         resolvable-effect question answers itself at a glance.

Detail is written to a sidecar file and NOT printed. Read it only when the
verdict looks wrong -- that is the whole point.

Usage:
  verdict.py <glob-dir> [--group REGEX] [--expect N] [--out FILE]
"""
import argparse, glob, json, os, re, statistics, sys, collections


def load(d):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            j = json.load(open(p))
        except Exception:
            continue
        recs = j if isinstance(j, list) else j.get("rows", [])
        if not isinstance(recs, list):
            continue
        for r in recs:
            if isinstance(r, dict) and "tps" in r:
                r = dict(r)
                r.setdefault("arm", os.path.basename(p)[:-5])
                r["_file"] = os.path.basename(p)
                rows.append(r)
    return rows


def arm_key(name, pattern):
    if not pattern:
        return name
    m = re.search(pattern, name)
    return m.group(0) if m else name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--group", help="regex; the matched span becomes the arm name")
    ap.add_argument("--expect", type=int, help="expected arm count (AFM-7)")
    ap.add_argument("--out", default=None, help="sidecar detail file")
    a = ap.parse_args()

    rows = load(a.dir)
    if not rows:
        print(f"NO PARSEABLE RESULTS in {a.dir}"); sys.exit(1)

    arms = collections.defaultdict(list)
    for r in rows:
        arms[arm_key(r.get("arm") or r["_file"], a.group)].append(r)

    print(f"{len(arms)} arms, {len(rows)} responses, from {a.dir}")
    if a.expect and len(arms) != a.expect:
        print(f"  *** ARM COUNT {len(arms)} != EXPECTED {a.expect} — RESULT IS INCOMPLETE ***")
    print()
    print(f"{'arm':<22} {'median':>8} {'spread':>8} {'accept':>8} {'stable':>7}  n")
    detail = {}
    for name in sorted(arms):
        g = arms[name]
        t = [r["tps"] for r in g]
        med = statistics.median(t)
        spread = (max(t) - min(t)) / med * 100 if med else 0
        dn = sum(r.get("draft_n") or 0 for r in g)
        da = sum(r.get("draft_accepted") or 0 for r in g)
        acc = f"{100*da/dn:.2f}%" if dn else "-"
        # AFM-6: do identical reps reproduce?
        byp = collections.defaultdict(set)
        for r in g:
            if r.get("draft_n") is not None:
                byp[r.get("prompt")].add((r["draft_n"], r["draft_accepted"]))
        unstable = sum(1 for v in byp.values() if len(v) > 1)
        stable = "yes" if unstable == 0 else f"{unstable} bad"
        print(f"{name:<22} {med:8.2f} {spread:7.1f}% {acc:>8} {stable:>7}  {len(g)}")
        # AFM-4: subgroup spread, kept in the sidecar not the console
        detail[name] = {"median": med, "mean": statistics.mean(t),
                        "spread_pct": spread, "acceptance": acc, "n": len(g),
                        "unstable_prompts": unstable,
                        "by_prompt": {p: {"tps": statistics.median(
                                              [r["tps"] for r in g if r.get("prompt") == p]),
                                          "acc": (lambda s: f"{100*s[1]/s[0]:.2f}%" if s[0] else "-")(
                                              (sum(r.get("draft_n") or 0 for r in g if r.get("prompt") == p),
                                               sum(r.get("draft_accepted") or 0 for r in g if r.get("prompt") == p)))}
                                      for p in sorted({r.get("prompt") for r in g if r.get("prompt")})}}

    # AFM-1: is the between-arm difference bigger than the within-arm noise?
    meds = {k: statistics.median([r["tps"] for r in v]) for k, v in arms.items()}
    if len(meds) > 1:
        lo, hi = min(meds.values()), max(meds.values())
        worst = max((max(r["tps"] for r in v) - min(r["tps"] for r in v)) / statistics.median([r["tps"] for r in v]) * 100
                    for v in arms.values())
        gap = (hi - lo) / lo * 100
        print(f"\nbetween-arm range {gap:.1f}%   worst within-arm spread {worst:.1f}%"
              f"   -> {'RESOLVABLE' if gap > worst else '*** NOT RESOLVABLE (AFM-1) ***'}")

    out = a.out or os.path.join(a.dir, "_verdict_detail.json")
    json.dump(detail, open(out, "w"), indent=1)
    print(f"detail -> {out}  (read only if the verdict looks wrong)")


if __name__ == "__main__":
    main()
