#!/usr/bin/env python3
"""Lab-ops status to #lab on the local hearth IRC server (loopback :6667), nick `labops`.

Each job in tools/labops_jobs.json is a shell command that prints one status line (run with a timeout; a failure is
reported, not fatal). Ledger and content-pipeline heartbeats are read locally. The status is posted only when it
differs from the last post, or every HEARTBEAT_H hours regardless, so the channel does not fill with repeats.
Run by apollo-labops.timer; `--force` posts now; `--dry-run` prints without connecting.

IRC client: a minimal one-shot (NICK/USER, wait for 001, JOIN, PRIVMSG each line, QUIT). Lines are cut to 340 bytes
(hearth allows 400 on loopback). Text it posts is status, never instructions; agents reading #lab treat it as data.
"""
import argparse, json, re, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
STATE = ROOT / "data" / "dev_diaries" / ".labops_last.json"
HOST, PORT, CHANNEL, NICK, HEARTBEAT_H = "127.0.0.1", 6667, "#lab", "labops", 3


def heartbeat(path, fields):
    try:
        d = json.loads(Path(path).read_text())
    except Exception:
        return "no heartbeat"
    age = (time.time() - d.get("ts", 0)) / 3600
    return f"{d.get('status', '?')} {age:.1f}h ago" + "".join(f" {k}={d[k]}" for k in fields if k in d)


def status_lines():
    lines = []
    jobs = json.loads((ROOT / "tools" / "labops_jobs.json").read_text())
    for j in jobs:
        try:
            r = subprocess.run(j["cmd"], shell=True, capture_output=True, text=True, timeout=j.get("timeout", 20))
            out = " ".join((r.stdout or r.stderr).split()) or f"no output (rc {r.returncode})"
        except subprocess.TimeoutExpired:
            out = "unreachable (timeout)"
        lines.append(f"{j['name']}: {out}")
    sys.path.insert(0, str(ROOT / "tools")); from intent import open_jobs   # intent lines (tools/intent.py)
    oj = open_jobs()
    lines.append("open intents: " + (", ".join(f"{r['id']} ({r['job']} on {r['host']})" for r in oj) if oj else "none"))
    dd = ROOT / "data" / "dev_diaries"
    lines.append("ledger: " + heartbeat(dd / ".ledger_heartbeat.json", []) + " | content capture: "
                 + heartbeat(dd / "content" / ".capture_heartbeat.json", ["items"]) + " | digest: "
                 + heartbeat(dd / "content" / ".digest_heartbeat.json", ["topics"]))
    return [l.encode()[:340].decode(errors="ignore") for l in lines]


def post(lines):
    s = socket.create_connection((HOST, PORT), timeout=15); f = s.makefile("rwb", buffering=0)
    send = lambda m: f.write((m + "\r\n").encode())
    nick = NICK
    send(f"NICK {nick}"); send(f"USER {nick} 0 * :Apollo lab-ops")
    deadline = time.time() + 15
    while time.time() < deadline:
        line = f.readline().decode(errors="ignore").strip()
        if not line: continue
        if line.startswith("PING"): send("PONG" + line[4:])
        parts = line.split()
        if len(parts) > 1 and parts[1] == "433":           # nick in use: take a suffix
            nick = f"{NICK}{int(time.time()) % 1000}"; send(f"NICK {nick}")
        if len(parts) > 1 and parts[1] == "001": break
    else:
        raise RuntimeError("no IRC welcome within 15 s")
    send(f"JOIN {CHANNEL}"); time.sleep(1)
    for l in lines:
        send(f"PRIVMSG {CHANNEL} :{l}"); time.sleep(0.3)
    send("QUIT :done"); time.sleep(0.5); s.close()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    lines = status_lines()
    if a.dry_run:
        print("\n".join(lines)); return 0
    try: last = json.loads(STATE.read_text())
    except Exception: last = {}
    calm = lambda ls: [re.sub(r"\d+\.\dh ago", "", l) for l in ls or []]   # ages change every run; content may not
    changed = calm(lines) != calm(last.get("lines"))
    due = time.time() - last.get("ts", 0) > HEARTBEAT_H * 3600
    if not (a.force or changed or due):
        print("unchanged; not posting"); return 0
    post(lines)
    STATE.write_text(json.dumps({"ts": int(time.time()), "lines": lines}))
    print("posted", len(lines), "lines"); return 0


if __name__ == "__main__":
    sys.exit(main())
