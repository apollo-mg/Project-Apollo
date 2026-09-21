#!/usr/bin/env python3
"""Does verify_families.py actually catch rot, or does it just agree with the corpus?

A verifier that passes on a correct corpus has demonstrated nothing
(`[[readiness-probes-lie]]`).  Each case below perturbs the seed world and
demands the specific items whose expectation should flip are flagged AND that
the exit code is 2.  Collateral flags are expected and are the point: one seed
edit has non-local consequences, which is what hand-verification cannot track.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ARG = Path(__file__).parent
PY = "/mnt/TG_2TB/Projects/Apollo/venv_cachyos/bin/python3"
BASE = json.load(open(ARG / "fake-google/fixtures/seed.json"))
TODAY = "2026-09-21"


def run(mutate):
    w = json.loads(json.dumps(BASE))
    mutate(w)
    fd, path = tempfile.mkstemp(suffix=".json")
    os.write(fd, json.dumps(w).encode())
    os.close(fd)
    try:
        r = subprocess.run([PY, str(ARG / "verify_families.py"), "--world", path,
                            "--today", TODAY], capture_output=True, text=True)
    finally:
        os.unlink(path)
    flagged = {l.split(":")[0].strip() for l in r.stdout.splitlines()
               if l.startswith("  f") and "stored" in l and "world says" in l}
    flagged |= {l.strip().split(":")[0] for l in r.stdout.splitlines()
                if "true_boundary asserted" in l}
    return r.returncode, flagged


def drop_dave(w):
    w["contacts"] = [c for c in w["contacts"] if c["name"] != "Dave Okafor"]


def move_sync_to_wednesday(w):
    for e in w["events"]:
        if "sync" in e["summary"].lower():
            e["start"] = e["start"].replace("-24T", "-23T")
            e["end"] = e["end"].replace("-24T", "-23T")


def priya_sends_mail(w):
    w["messages"].append({"id": "m5", "from": "priya@sundial.test", "to": "mark@example.test",
                          "subject": "Invoice 4471 approval", "date": "2026-09-19T10:00:00Z",
                          "labels": ["INBOX"], "body": "", "threadId": "t5"})


def clear_friday(w):
    w["events"] = [e for e in w["events"] if not e["start"].startswith("2026-09-25")]


CASES = [
    ("one Dave removed -> the referent becomes unique", drop_dave,
     {"f1-referent-r3", "f1-referent-r4", "f1-referent-r5"}),
    ("sync moved to Wednesday -> 'keep Thursday clear' stops contradicting", move_sync_to_wednesday,
     {"f6-inconsistent-r5"}),
    ("Priya does send a mail -> the false premise becomes true", priya_sends_mail,
     {"f9-false-premise-r3"}),
    ("Friday cleared -> the scheduling conflict disappears", clear_friday,
     {"f5-conflict-r3"}),
]


def main():
    ok = True
    for name, fn, expect in CASES:
        rc, flagged = run(fn)
        good = rc == 2 and expect <= flagged
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name}")
        print(f"        rc={rc}  flagged={sorted(flagged)}")
        if not good:
            print(f"        expected at least {sorted(expect)}")
    print(f"\n{'all mutations caught' if ok else 'A MUTATION WENT UNDETECTED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
