#!/usr/bin/env python3
"""Classify RUNAWAY scenarios in an argus results.jsonl.

Greedy decoding cannot sample out of a degenerate state, so a low-bit model can loop until the
token budget or the timeout. Unscreened, that misreads either as a decision failure or as VOID.
Spec is in data/receipts/agentic-ladder/PREREG_AGENTIC_LADDER.md Amendment 1, written before data.

Four signals; TWO trip a RUNAWAY, ONE flags for manual review.
"""
import json, sys, statistics, collections, argparse, re

def ngrams(text, n=12):
    w = re.findall(r"\S+", text or "")
    return [" ".join(w[i:i+n]) for i in range(max(0, len(w)-n+1))]

def screen(rows):
    times = [r.get("secs", 0) or 0 for r in rows]
    med = statistics.median(times) if times else 0
    out = []
    for r in rows:
        sig = []
        secs = r.get("secs", 0) or 0
        if med > 0 and secs > 3 * med:
            sig.append(f"time {secs:.0f}s > 3x median {med:.0f}s")
        rep = collections.Counter(ngrams(r.get("reply", "")))
        if rep:
            g, c = rep.most_common(1)[0]
            if c >= 4:
                sig.append(f"12-gram x{c}")
        tc = r.get("tool_calls") or []
        keys = [json.dumps(t, sort_keys=True) if isinstance(t, dict) else str(t) for t in tc]
        run = best = 1
        for i in range(1, len(keys)):
            run = run + 1 if keys[i] == keys[i-1] else 1
            best = max(best, run)
        if best >= 4:
            sig.append(f"same tool call x{best}")
        why = (r.get("why") or "") + " " + (r.get("verdict") or "")
        if re.search(r"truncat|length|max.?token", why, re.I):
            sig.append("length-truncated")
        out.append((r.get("id"), r.get("verdict"), secs, sig))
    return out, med

ap = argparse.ArgumentParser(); ap.add_argument("results"); ap.add_argument("--pass-size", type=int, default=16)
a = ap.parse_args()
rows = [json.loads(l) for l in open(a.results) if l.strip()]
res, med = screen(rows)
runaway = [r for r in res if len(r[3]) >= 2]
review  = [r for r in res if len(r[3]) == 1]
print(f"{len(rows)} rows, median scenario time {med:.0f}s\n")
print(f"RUNAWAY (>=2 signals): {len(runaway)}")
for i, v, s, sg in runaway: print(f"   {i:<26} {v:<11} {s:6.0f}s  :: {'; '.join(sg)}")
print(f"\nflagged for review (1 signal): {len(review)}")
for i, v, s, sg in review: print(f"   {i:<26} {v:<11} {s:6.0f}s  :: {'; '.join(sg)}")
print(f"\nclean: {len(res)-len(runaway)-len(review)}")
n = len(rows) // a.pass_size if a.pass_size else 1
if n:
    print(f"\ngate rule: RUNAWAY on more than 4 of {a.pass_size} -> temp 0 unusable, revert to temp 0.6")
    print(f"  observed: {len(runaway)} runaway across {len(rows)} rows "
          f"({len(runaway)/max(1,n):.1f} per {a.pass_size}-scenario pass)")
