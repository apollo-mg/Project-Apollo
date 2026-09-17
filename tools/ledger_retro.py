#!/usr/bin/env python3
"""Ledger retrospective — cross-corpus aggregate mining over data/dev_diaries/.

The per-entry system (ledger_index/query) answers specific questions semantically. This does the
thing it can't: aggregate the mechanically-extractable skeleton the LEDGER_SPEC defines (errors,
retry-loops, corrections) across ALL diary parts, to surface recurring-failure RATES over time and
a rough self-calibration score. Pattern-based by design (the SPEC's own principle: extract
mechanically, don't ask a model to discover what mattered).

Usage:  ledger_retro.py [dev_diaries_dir]   (default data/dev_diaries)
"""
import os, re, sys, glob, datetime
from collections import defaultdict, Counter

DIR = sys.argv[1] if len(sys.argv) > 1 else "data/dev_diaries"

# Recurring-failure taxonomy — signatures for the mistakes the ledger honestly records.
FAILURES = {
    "pgrep/pkill -f self-match":   r"p(?:grep|kill)\s+-f|self[- ]match|exit\s+255",
    "partial-arm / rep-0 read":    r"partial[- ]arm|rep[- ]?0\b|<\s*3\s*rep|median.*partial",
    "edit-before-read":            r"edit[- ]before[- ]read|has not been read|File has not been read",
    "fish for-loop parse error":   r"fish.*(?:for|loop).*parse|parse error near .?end",
    "readiness probe lied / vacuous": r"readiness.prob|vacuous|rc\s*=?\s*0.*(?:not|isn.t) proof|exit(?:ed)? 0.*(?:fail|error)",
    "low-memory reaper kill":      r"low.memory|reaper|reaped|background.*(?:killed|stopped).*memory",
    "rounded-size false mismatch": r"rounded.*size|false.*(?:mismatch|corrupt)|byte-exact",
    "stale marker / pidfile":      r"stale.*(?:marker|log|partial)|pidfile.*success|waiter.*stale",
    "name collision":              r"name[- ]collision|collision.*(?:provenance|mmproj)",
}
# Calibration markers — self-corrections (a prediction/claim that was wrong) vs confirmations.
WRONG = re.compile(r"correction to my own|hypothesis flipped|i was wrong|over[- ]?read|walk(?:ed)? .*back|retract|mis(?:read|assigned|stated)|falsified.*my|i .*over[- ]", re.I)
RIGHT = re.compile(r"prediction held|as predicted|right this time|\bCONFIRMED\b|confirmed.*(?:predict|hypoth)|bit-identical.*confirm", re.I)

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

def main():
    files = sorted(glob.glob(os.path.join(DIR, "*_diary.md")) + glob.glob(os.path.join(DIR, "*_ledger.md")))
    if not files:
        print(f"no diary files in {DIR}"); return
    fail_files = defaultdict(set)     # signature -> set of files it appears in
    fail_by_day = defaultdict(Counter)  # day -> Counter(signature)
    wrong_hits, right_hits, wrong_samples = 0, 0, []
    days = set()
    comp = {k: re.compile(v, re.I) for k, v in FAILURES.items()}
    for f in files:
        m = DATE_RE.search(os.path.basename(f))
        day = m.group(1) if m else "?"
        days.add(day)
        txt = open(f, errors="replace").read()
        for name, pat in comp.items():
            if pat.search(txt):
                fail_files[name].add(f)
                fail_by_day[day][name] += 1
        for mo in WRONG.finditer(txt):
            wrong_hits += 1
            line = txt[max(0, mo.start()-40):mo.start()+60].replace("\n", " ")
            if len(wrong_samples) < 6: wrong_samples.append((day, line.strip()))
        right_hits += len(RIGHT.findall(txt))

    print(f"=== Ledger retrospective — {len(files)} diary parts, {len(days)} days "
          f"({min(days)} .. {max(days)}) ===\n")
    print("RECURRING FAILURES  (diary-parts where each appeared, of "
          f"{len(files)} total)\n" + "-"*64)
    for name, fs in sorted(fail_files.items(), key=lambda kv: -len(kv[1])):
        pdays = sorted({DATE_RE.search(os.path.basename(x)).group(1) for x in fs if DATE_RE.search(os.path.basename(x))})
        rate = 100*len(fs)/len(files)
        print(f"  {name:34s} {len(fs):3d} parts ({rate:4.1f}%)  {len(pdays)} days  "
              f"first {pdays[0] if pdays else '?'}  last {pdays[-1] if pdays else '?'}")
    print(f"\nCALIBRATION  (rough, keyword-based)\n" + "-"*64)
    tot = wrong_hits + right_hits
    print(f"  self-corrections / 'I was wrong' markers: {wrong_hits}")
    print(f"  confirmations / 'as predicted' markers:   {right_hits}")
    if tot:
        print(f"  right-when-called rate ~ {100*right_hits/tot:.0f}% (of {tot} scored claims)")
    print("  sample self-corrections:")
    for day, s in wrong_samples:
        print(f"    [{day}] ...{s}...")

if __name__ == "__main__":
    main()
