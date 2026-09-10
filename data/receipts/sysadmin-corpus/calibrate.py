#!/usr/bin/env python3
"""Calibration gate: the harness must reproduce the REFERENCE TRACE before it measures anything.

Every instrument defect found on 2026-09-02 -- whole-file returns, snapshot-only replay, a grader
that read one field, a check regex matching the wrong path -- would have been caught in seconds by
replaying Claude's own known-good commands and checking the outputs were what Claude actually saw.
Instead the harness was built, pointed at a model, and the model's confusion was read as a result.

This is the control arm for the instrument. An item is not ready until this passes.
"""
import sys, json
from replay_exec import ExecReplay

# (command, substring that MUST appear, substring that must NOT appear)
TRACE = [
    ("dkms build nct6687d/1",
     "nct6687.c:444", "nct6687.c:445"),
    ("sed -n '444p' /var/lib/dkms/nct6687d/1/build/nct6687.c",
     "strncpy(valcp, val, 16)", "SPDX"),
    ("grep -n 'string.h' /var/lib/dkms/nct6687d/1/build/nct6687.c",
     "", "SPDX"),
    ("sed -i '/#include <linux\\/slab.h>/a #include <linux/string.h>' /usr/src/nct6687d-1/nct6687.c",
     "edit applied", ""),
    ("grep -n 'string.h' /var/lib/dkms/nct6687d/1/build/nct6687.c",
     "linux/string.h", "SPDX"),
    ("dkms build nct6687d/1",
     "nct6687.c:445", "nct6687.c:444"),          # THE trigger: displacement by the inserted line
    ("grep -n 'strncpy' /usr/lib/modules/7.2.2-1-cachyos/build/include/linux/string.h",
     "Preferred to strncpy", ""),
    ("sed -i 's/strncpy(valcp, val, 16)/strscpy(valcp, val, sizeof(valcp))/' /usr/src/nct6687d-1/nct6687.c",
     "edit applied", ""),
    ("dkms build nct6687d/1",
     "exit code: 0", "error:"),
]


# Cases harvested from VOIDED runs. The gate passed on a broken harness because the reference
# trace never used grep alternation or ls'd a nonexistent path -- the models did, and lost 32%
# and 44% of their turns respectively. Every voided run is a source of new gate cases.
HARVESTED = [
    # 27B lost 8/25 turns to this: naive pipeline split broke grep alternation
    ("grep -n 'strncpy\\|strcmp' /var/lib/dkms/nct6687d/1/build/nct6687.c",
     "444:", "not in the read-only whitelist"),
    # Flash-Next lost 11/25 turns descending a fabricated directory tree
    ("ls /var/lib/dkms/nct6687d/nct6687d/",
     "No such file or directory", "nct6687d\n"),
    # the header must behave as a FILE, not as pre-filtered grep output
    ("grep -c strncpy /usr/lib/modules/7.2.2-1-cachyos/build/include/linux/string.h",
     "5", "Preferred to"),
    ("grep -cE '^\\s*(extern )?char \\*strncpy' /usr/lib/modules/7.2.2-1-cachyos/build/include/linux/string.h",
     "0", "Preferred to"),
]

def main(state_dir):
    fails = []
    # TRACE mutates the source (prepatch -> includeonly -> strscpy), so HARVESTED cases -- which
    # all assume the as-found state -- need a FRESH replay. Running them after TRACE checked
    # line 444 against a file where strncpy had already been replaced.
    sh = ExecReplay(state_dir)
    for i, (cmd, must, mustnt) in enumerate(TRACE):
        out = sh.run(cmd)
        if must and must not in out:
            fails.append(f"step {i}: missing {must!r}\n    cmd: {cmd[:70]}\n    got: {out[:110]!r}")
        if mustnt and mustnt in out:
            fails.append(f"step {i}: contains forbidden {mustnt!r}\n    cmd: {cmd[:70]}\n    got: {out[:110]!r}")
    sh = ExecReplay(state_dir)          # fresh: harvested cases assume the as-found state
    for j, (cmd, must, mustnt) in enumerate(HARVESTED, start=len(TRACE)):
        out = sh.run(cmd)
        if must and must not in out:
            fails.append(f"step {j} (harvested): missing {must!r}\n    cmd: {cmd[:70]}\n    got: {out[:110]!r}")
        if mustnt and mustnt in out:
            fails.append(f"step {j} (harvested): contains {mustnt!r}\n    cmd: {cmd[:70]}\n    got: {out[:110]!r}")
    if fails:
        print("CALIBRATION FAILED — the harness does not reproduce the reference trace:")
        for f in fails: print("  " + f)
        return 1
    n=len(TRACE)+len(HARVESTED)
    print(f"CALIBRATION PASSED — {n}/{n} steps ({len(TRACE)} reference + {len(HARVESTED)} harvested from voided runs)")
    print("  including the 444 -> 445 displacement that is this item's discriminator")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "item02_dkms_strncpy_removed/state"))
