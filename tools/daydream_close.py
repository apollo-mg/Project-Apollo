#!/usr/bin/env python3
"""Close daydream threads by hand after checking them: the 'Likely closed by a commit' list in a morning brief, or an
outcome that only ever happened in chat (09-30: the Dolphin fix was confirmed in chat, never in the diary, so the
nightly closure check had nothing to find). Writes status=closed, closed_on, closed_by, closed_why to threads_state.json.
Also answers the brief's question (2026-11-02): finish keeps the thread open and lists it under "You said finish",
drop closes it, park hides it for --days (default 30), note records a fact (--why) and keeps it open.

usage: daydream_close.py --by "<evidence>" --why "<one sentence>" ID [ID ...]
       daydream_close.py --likely [DATE]   close every thread in DATE's 'Likely closed by a commit' list (default today),
                                           each with its own commit as evidence
       daydream_close.py --answer finish|drop|park|note [--why "..."] [--days N] ID
       add --dry-run to print without writing"""
import argparse, datetime, json, re, sys
from pathlib import Path

M = Path(__file__).resolve().parents[1] / "data" / "dev_diaries" / "morning"


def answer(t, kind, why, today, days):
    """Apply Mark's answer to one thread (pure, for the tests)."""
    t.update(answer=kind, answered_on=today, answer_why=why)
    if kind == "drop":
        t.update(status="closed", closed_on=today, closed_by="dropped by Mark", closed_why=why)
    elif kind == "park":
        t.update(status="parked", park_until=(datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat())
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--by"); ap.add_argument("--why", default="confirmed by a session or Mark")
    ap.add_argument("--likely", nargs="?", const=datetime.date.today().isoformat())
    ap.add_argument("--answer", choices=["finish", "drop", "park", "note"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sp = M / "threads_state.json"; state = json.load(open(sp)); today = datetime.date.today().isoformat()
    if a.answer:
        if not a.ids:
            ap.error("--answer needs a thread ID")
        why = a.why if a.why != ap.get_default("why") else f"Mark answered {a.answer}"
        for k in a.ids:
            t = state["threads"].get(k)
            if t is None:
                print(f"SKIP {k}: no such thread"); continue
            print(f"{a.answer} {k}: {re.sub(r'[*`]', '', t['text'])[:90]}  ({why})")
            if not a.dry_run:
                answer(t, a.answer, why, today, a.days)
        if not a.dry_run:
            json.dump(state, open(sp, "w"), indent=1, ensure_ascii=False)
        return
    todo = []
    if a.likely:
        v = json.load(open(M / f"verdicts_{a.likely}.json"))["verdicts"]
        todo = [(k, d["ev"]["source"], d.get("why") or a.why) for k, d in v.items()
                if d.get("status") == "suggested" and d.get("ev", {}).get("source", "").startswith("commit ")]
    elif a.ids and a.by:
        todo = [(k, a.by, a.why) for k in a.ids]
    else:
        ap.error("give IDs with --by, or --likely, or --answer with an ID")
    for k, by, why in todo:
        t = state["threads"].get(k)
        if t is None:
            print(f"SKIP {k}: no such thread"); continue
        if t["status"] != "open":
            print(f"SKIP {k}: already {t['status']}"); continue
        print(f"close {k}: {re.sub(r'[*`]', '', t['text'])[:90]}  <- {by}")
        if not a.dry_run:
            t.update(status="closed", closed_on=today, closed_by=by, closed_why=why)
    if not a.dry_run:
        json.dump(state, open(sp, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
