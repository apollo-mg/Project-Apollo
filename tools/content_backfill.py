#!/usr/bin/env python3
"""One-off: run tools/content_capture.py over past ledger windows, so the first content sheet has a week of material.

Each diary section (`## HH:MM -- N events` in data/dev_diaries/<date>_ledger.md) closes a window that began at the
previous section. The transcript is sliced by record timestamp into those windows, each slice goes through
ledger_extract.py with a THROWAWAY state file (the ledger's own .ledger_state.json is never touched, or the next diary
window would be silently skipped), and the capture runs with that section as its diary context.

.73 slot hygiene as in ledger_run.sh: snapshot the slots before the first call and erase the ones this run changed
on the way out, so none of these chats is saved at the next suspend.

    content_backfill.py --since 2026-10-11 [--until 2026-10-17] [--dry-run]
"""
import argparse, json, os, re, subprocess, sys, tempfile
from datetime import datetime, timedelta

ROOT = "/mnt/TG_2TB/Projects/Apollo"
PY = f"{ROOT}/venv_cachyos/bin/python3"
PROJ = os.path.expanduser("~/.claude/projects/-mnt-TG-2TB-Projects-Apollo")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_capture as cc  # noqa: E402

HDR = re.compile(r"(?m)^## (\d\d:\d\d) \S+ (\d+) events\s*$")
TS = re.compile(r'"timestamp":"(\d{4}-\d\d-\d\dT[\d:.]+Z)"')

def sections(since, until):
    out, d = [], since
    while d <= until:
        p = f"{ROOT}/data/dev_diaries/{d:%Y-%m-%d}_ledger.md"
        if os.path.exists(p):
            s = open(p).read(); hs = list(HDR.finditer(s))
            for k, h in enumerate(hs):
                body = s[h.end(): hs[k + 1].start() if k + 1 < len(hs) else len(s)]
                end = datetime.strptime(f"{d:%Y-%m-%d} {h.group(1)}", "%Y-%m-%d %H:%M")
                out.append((end, re.sub(r"(?s)<details>.*?</details>", "", body).strip()))
        d += timedelta(days=1)
    return sorted(out)

def main(a):
    since, until = (datetime.strptime(x, "%Y-%m-%d") for x in (a.since, a.until))
    secs = sections(since, until)
    if not secs: print("no diary sections in range"); return 1
    bounds = [(secs[0][0] - timedelta(hours=3), secs[0][0])] + [(secs[k - 1][0], secs[k][0]) for k in range(1, len(secs))]
    tmp = tempfile.mkdtemp(prefix="content_backfill_")
    files = [open(f"{tmp}/w{k:03d}.jsonl", "w") for k in range(len(secs))]
    k, cur = 0, None
    with open(a.transcript, errors="replace") as f:      # one pass; records without a timestamp stay in the current window
        for ln in f:
            m = TS.search(ln[:400]) or TS.search(ln)
            if m:
                cur = datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
            if cur is None or cur < bounds[0][0] or cur >= bounds[-1][1]: continue
            while k < len(bounds) - 1 and cur >= bounds[k][1]: k += 1
            files[k].write(ln)
    for fh in files: fh.close()
    deny = cc.load_deny(a.deny)
    snap = f"{tmp}/slots.json"
    if not a.dry_run: subprocess.run([PY, f"{ROOT}/tools/slot_erase.py", "snapshot", snap], capture_output=True)
    try:
        for k, (end, body) in enumerate(secs):
            st = f"{tmp}/state.json"
            ev = subprocess.run([PY, f"{ROOT}/tools/ledger_extract.py", f"{tmp}/w{k:03d}.jsonl", "--state", st],
                                capture_output=True, text=True).stdout.splitlines()
            diary = "\n\n".join(p for p in re.split(r"\n\s*\n", body) if p.strip() and not cc.denied(p, deny))
            label = end.strftime("%Y-%m-%d %H:%M")
            try:
                res = cc.capture(ev, a.host, diary, label, "backfill", deny, a.out, dry_run=a.dry_run,
                                 max_chunks=12) if not a.dry_run else {"status": "dry-run", "events": len(ev)}
            except Exception as e:
                res = {"status": "error", "reason": f"{type(e).__name__}: {str(e)[:120]}"}
            print(json.dumps({"window": label, "since": bounds[k][0].strftime("%m-%d %H:%M"), **res}), flush=True)
    finally:
        if not a.dry_run:
            r = subprocess.run([PY, f"{ROOT}/tools/slot_erase.py", "erase-changed", snap], capture_output=True, text=True)
            print(r.stdout.strip().replace("\n", " | "), flush=True)
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--since", required=True)
    p.add_argument("--until", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--transcript", default=max((os.path.join(PROJ, x) for x in os.listdir(PROJ) if x.endswith(".jsonl")),
                                               key=os.path.getmtime))
    p.add_argument("--host", default="http://127.0.0.1:8099")
    p.add_argument("--deny", default=f"{cc.CDIR}/private_terms.txt")
    p.add_argument("--out", default=f"{cc.CDIR}/candidates.jsonl")
    p.add_argument("--dry-run", action="store_true", help="slice and extract only; no model calls")
    sys.exit(main(p.parse_args()))
