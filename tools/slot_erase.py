#!/usr/bin/env python3
"""Erase the .73 llama-server slots that an automated job used, and only those (2026-10-05).

Why: the daily server runs --resume. Every slot's conversation is saved at shutdown and restored at the next start,
at ~3.8 ms per token, and the restore blocks /health. On 10-04/05 every wake restored the LEDGER's own summarisation
chats (~11.7k tokens, ~45 s per wake), because nothing replaced them. Erasing every idle slot (the daydream's first
version) would also drop a conversation of Mark's that the job never touched. So: snapshot each slot's id_task
before the job, then erase the idle slots whose id_task changed. If the node is asleep at snapshot time, the
server starts fresh for the job, so any slot with a task afterwards is the job's.

usage: slot_erase.py snapshot FILE        record {slot id: id_task}; {} if the node is unreachable
       slot_erase.py erase-changed FILE   erase idle slots whose id_task differs from FILE; prints one line each
       slot_erase.py --self-test
POST /slots/<id>?action=erase goes to the node directly (NODE_LLAMA, default http://10.0.0.73:8080): the wake
proxy forwards GET /slots but not the POST action."""
import json, os, sys, urllib.request

NODE = os.environ.get("NODE_LLAMA", "http://10.0.0.73:8080").rstrip("/")


def get_slots(timeout=5):
    with urllib.request.urlopen(NODE + "/slots", timeout=timeout) as r:
        return json.load(r)


def task_map(slots):
    return {str(s["id"]): s.get("id_task") for s in slots}


def to_erase(before, slots):
    """Idle slots that ran a task since the snapshot. before: {id: id_task} from snapshot (possibly {})."""
    return [s["id"] for s in slots
            if not s.get("is_processing") and s.get("id_task") is not None
            and before.get(str(s["id"])) != s.get("id_task")]


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    if len(argv) != 2 or argv[0] not in ("snapshot", "erase-changed"):
        print(__doc__, file=sys.stderr); return 2
    cmd, path = argv
    if cmd == "snapshot":
        try:
            m = task_map(get_slots())
        except Exception as e:                       # asleep or down: the job's own wake starts a fresh server
            print(f"slots: snapshot empty ({type(e).__name__})")
            m = {}
        json.dump(m, open(path, "w"))
        return 0
    try:
        before = json.load(open(path))
    except Exception:
        before = {}
    try:
        slots = get_slots(timeout=10)
    except Exception as e:
        print(f"slots: node unreachable ({type(e).__name__}), nothing erased"); return 0
    ids = to_erase(before, slots)
    for i in ids:
        try:
            req = urllib.request.Request(f"{NODE}/slots/{i}?action=erase", method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"erase slot {i}: {r.read().decode()[:120]}")
        except Exception as e:
            print(f"erase slot {i}: FAILED {type(e).__name__}")
    print(f"slots erased: {' '.join(map(str, ids)) or 'none'}")
    return 0


def self_test():
    fails = []
    def check(m, c):
        print(("PASS  " if c else "FAIL  ") + m); fails.append(m) if not c else None
    restored = [{"id": 0}, {"id": 1}]                                    # fresh start: restored slots carry no task
    check("restored, untouched slots are kept", to_erase({}, restored) == [])
    after = [{"id": 0, "id_task": 5}, {"id": 1}]
    check("node asleep at snapshot: the slot the job used is erased, the other kept", to_erase({}, after) == [0])
    before = {"0": 12, "1": 40}
    after = [{"id": 0, "id_task": 12}, {"id": 1, "id_task": 57}]
    check("node awake: only the slot whose task changed is erased", to_erase(before, after) == [1])
    after = [{"id": 0, "id_task": 70, "is_processing": True}, {"id": 1, "id_task": 57}]
    check("a slot still processing (someone else's request) is never erased", to_erase(before, after) == [1])
    check("no change, nothing erased", to_erase(before, [{"id": 0, "id_task": 12}, {"id": 1, "id_task": 40}]) == [])
    print("self-test:", "FAILED" if fails else "all passed"); return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
