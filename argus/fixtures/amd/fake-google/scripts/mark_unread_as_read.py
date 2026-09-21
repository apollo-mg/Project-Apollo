#!/usr/bin/env python3
"""Walk unread Gmail messages, flip UNREAD->READ (keeping other labels), and record an
audit entry per message so the change is real and scoreable.

There is no `markasread` action on this backend, so state lives in mailbox/state.json:
remove UNREAD, add READ, leave INBOX etc untouched, append one audit[] entry per message,
then re-run the same search — empty result means done.
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("ARGUS_STATE", ROOT / "state.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="is:unread")
    ap.add_argument("--max", type=int, default=100000)
    a = ap.parse_args()

    if not STATE.exists():
        sys.exit(f"state.json missing (have {STATE})")
    s = json.loads(STATE.read_text())

    def matches(m, q):
        q = (q or "").strip().lower()
        if not q:
            return True
        for term in q.split():
            if term == "is:unread":
                if "UNREAD" not in m["labels"]:
                    return False
            else:
                hay = (f"{m['subject']} {m.get('body','')} {m.get('from','')}").lower()
                if term not in hay:
                    return False
        return True

    to_mark = [m for m in s["messages"]
               if "UNREAD" in m["labels"] and matches(m, a.query)][:a.max]
    marked = []

    for m in to_mark:
        before = list(m["labels"])
        after = [l for l in m["labels"] if l != "UNREAD"] + ["READ"]
        if before == after:
            continue
        m["labels"] = after
        s["audit"].append({
            "action": "gmail.markasread",
            "message_id": m["id"],
            "threadId": m["threadId"],
            "ids": [m["id"]],
            "before_labels": before,
            "after_labels": after,
        })
        marked.append(m["id"])

    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=2))
    tmp.replace(STATE)  # atomic

    print({"marked_read": marked})


if __name__ == "__main__":
    main()
