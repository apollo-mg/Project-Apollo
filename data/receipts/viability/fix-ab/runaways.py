#!/usr/bin/env python3
"""Runaway generations in llama-server logs -- the secondary rule from the fix-ab amendment.
Registered wording: a runaway is a generation whose n_gen reaches THRESH tokens and that either
completes at the -n 4096 cap or is cancelled while generating. A long generation that stops by
itself below the cap is NOT a runaway; it is reported separately as 'self-terminated', so every
reading of the rule can be checked. The primary rule (completions at the cap) is printed too."""
import glob, os, re, sys
THRESH, CAP = 1000, 4096
PROG = re.compile(r"task (\d+) \| n_gen = +(\d+)")
DONE = re.compile(r"task (\d+) \| +eval time = +[\d.]+ ms / +(\d+) tokens")
CANCEL = re.compile(r"cancel task, id_task = (\d+)")
RESET = re.compile(r"task (\d+) \| vbr reset:")

def scan(path):
    mx, comp, canc, resets = {}, {}, set(), set()
    for l in open(path, errors="replace"):
        if (m := PROG.search(l)):
            mx[m[1]] = max(mx.get(m[1], 0), int(m[2]))
        elif (m := DONE.search(l)) and "prompt eval" not in l:
            comp[m[1]] = int(m[2]); mx[m[1]] = max(mx.get(m[1], 0), int(m[2]))
        elif (m := CANCEL.search(l)):
            canc.add(m[1])
        elif (m := RESET.search(l)):
            resets.add(m[1])
    long_ = [t for t, n in mx.items() if n >= THRESH]
    at_cap = [t for t in long_ if comp.get(t) == CAP]
    cut = [t for t in long_ if t not in comp and t in canc]
    selfterm = [t for t in long_ if t in comp and comp[t] < CAP]
    run = at_cap + cut
    return {"resets": len(resets), "primary": sum(n == CAP for n in comp.values()), "runaway": len(run),
            "at_cap": len(at_cap), "cancelled": len(cut), "after_reset": sum(t in resets for t in run),
            "selfterm_long": len(selfterm), "normal_max": max([n for n in mx.values() if n < THRESH] or [0])}

KEYS = ("resets", "primary", "runaway", "at_cap", "cancelled", "after_reset", "selfterm_long")
for d in sys.argv[1:]:
    print(f"== {d}")
    arms = {}
    for f in sorted(glob.glob(os.path.join(d, "server_*.log"))):
        tag = os.path.basename(f)[7:-4]; r = scan(f)
        a = arms.setdefault(re.sub(r"\d+$", "", tag), {k: 0 for k in KEYS} | {"runs": 0})
        a["runs"] += 1
        for k in KEYS:
            a[k] += r[k]
        print(f"   {tag:9s} resets {r['resets']:3d}  primary {r['primary']}  runaway {r['runaway']} "
              f"(at cap {r['at_cap']}, cancelled {r['cancelled']}; after a reset {r['after_reset']})  "
              f"self-terminated >=1000: {r['selfterm_long']}  normal max {r['normal_max']}")
    for arm, a in arms.items():
        print(f"   -> {arm:7s} {a['runs']} runs, resets {a['resets']:3d}, runaways {a['runaway']} "
              f"(after a reset {a['after_reset']}, cancelled {a['cancelled']}), self-terminated long {a['selfterm_long']}")
