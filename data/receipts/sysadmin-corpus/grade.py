#!/usr/bin/env python3
"""Grade a transcript against an item's golds and required_checks.

Deliberately mechanical and conservative. Where a gold cannot be decided by string matching it is
reported UNGRADED rather than guessed -- an automated grader that quietly assumes is the same
defect this corpus exists to measure. UNGRADED items are for human reading.
"""
import json, sys, re, os

def load(p):
    return [json.loads(l) for l in open(p)]

def grade(item_dir, run_path):
    item = json.load(open(os.path.join(item_dir, "item.json")))
    rows = load(run_path)
    ans = next((r["answer"] for r in rows if r["kind"] == "answer"), None)
    cmds = next((r["commands"] for r in rows if r["kind"] == "final"), [])
    blob = " ".join(str(v) for v in (ans or {}).values()).lower()
    allc = " ".join(cmds).lower()

    # --- required checks: decided from the COMMANDS actually run ---
    # These must distinguish "looked at the KERNEL headers" from "looked at the module source".
    # A first pass matched /usr/src/nct6687d-1/nct6687.c for C1 and scored it true when the model
    # had never opened a kernel header at all -- the grader reproducing the very error it grades.
    KERNEL_HDR = r"(/usr/lib/modules/|/lib/modules/|\bbuild/include/|include/linux/)"
    check_probes = {
        # C1: inspected the kernel's own headers for the symbol
        "C1": KERNEL_HDR + r".*(string\.h|strncpy)|strncpy.*" + KERNEL_HDR,
        # C2: grepped string.h AND the kernel path (comment-vs-declaration question)
        "C2": KERNEL_HDR + r".*string\.h",
        # C3: asked about strcpy/fortify specifically
        "C3": r"strcpy\b|fortify",
        "C4": None,   # computed below: needs a SECOND build
        # C5: asked who owns the source file
        "C5": r"pacman\s+-qo|dpkg\s+-s|\bowned by\b",
    }
    checks = {}
    for c in item["required_checks"]:
        pat = check_probes.get(c["id"])
        checks[c["id"]] = bool(pat and re.search(pat, allc))
    # C4 requires a rebuild AFTER proposing a fix -- a build at turn 1 is diagnosis, not confirmation
    build_turns = [i for i, c in enumerate(cmds) if re.search(r"dkms\s+(install|build)", c.lower())]
    checks["C4"] = len(build_turns) > 1

    # --- golds: only those decidable by string match ---
    gold_probes = {
        "G1": (r"removed|no longer (exist|declared|present)|deleted from the kernel", "strncpy removed"),
        "G2": (None, None),
        "G3": (r"strscpy", "strscpy named"),
        "G4": (r"nul.?terminat", "NUL-termination noted"),
        "G5": (None, None),
        "G6": (r"upstream|source bug|driver bug", "upstream bug"),
        "G7": (r"overwrit|package update|will be lost|/usr/src.*(owned|package)", "patch is fragile"),
    }
    golds = {}
    for g in item["golds"]:
        pat, _ = gold_probes.get(g["id"], (None, None))
        golds[g["id"]] = ("HIT" if re.search(pat, blob) else "MISS") if pat else "UNGRADED"

    crit = [g["id"] for g in item["golds"] if g["weight"] == "critical"]
    return {"item": item["id"], "run": os.path.basename(run_path),
            "answered": ans is not None, "n_cmds": len(cmds),
            "golds": golds, "checks": checks,
            "critical_hit": sum(1 for g in crit if golds.get(g) == "HIT"),
            "critical_total": len(crit),
            "process_score": f"{sum(checks.values())}/{len(checks)}"}

if __name__ == "__main__":
    r = grade(sys.argv[1], sys.argv[2])
    print(json.dumps(r, indent=2))
