#!/usr/bin/env python3
"""Runaway generations in llama-server logs -- the secondary rule from the fix-ab amendment.
A runaway: a generation whose n_gen reaches THRESH tokens, whether it completes or is cancelled.
Also prints the primary rule (completions at the 4096 cap) so the two can be compared per log."""
import glob, os, re, sys
THRESH = 1000
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
    run = [t for t, n in mx.items() if n >= THRESH]
    return {"resets": len(resets), "primary": sum(n == 4096 for n in comp.values()), "runaway": len(run),
            "cancelled": sum(t in canc and t not in comp for t in run), "after_reset": sum(t in resets for t in run),
            "grey_500_999": sum(500 <= n < THRESH for n in mx.values()),
            "normal_max": max([n for n in mx.values() if n < THRESH] or [0])}

for d in sys.argv[1:]:
    print(f"== {d}")
    arms = {}
    for f in sorted(glob.glob(os.path.join(d, "server_*.log"))):
        tag = os.path.basename(f)[7:-4]; r = scan(f)
        arm = re.sub(r"\d+$", "", tag); a = arms.setdefault(arm, {k: 0 for k in r}); a["normal_max"] = max(a["normal_max"], r["normal_max"])
        for k in r:
            if k != "normal_max": a[k] += r[k]
        print(f"   {tag:9s} resets {r['resets']:3d}  primary(4096) {r['primary']}  runaway(>=1000) {r['runaway']} "
              f"[cancelled {r['cancelled']}, after reset {r['after_reset']}]  grey 500-999: {r['grey_500_999']}  normal max {r['normal_max']}")
    for arm, a in arms.items():
        print(f"   -> {arm:7s} resets {a['resets']:3d}  primary {a['primary']}  runaway {a['runaway']} (cancelled {a['cancelled']}, after reset {a['after_reset']})  normal max {a['normal_max']}")
