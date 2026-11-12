#!/usr/bin/env python3
"""Observer, phase 1 (2026-11-11): plain checks on the runs we launch, every five minutes, with no model involved.

WHY: this week a GPQA run slowed for hours unnoticed, three questions sat stuck behind a runner bug, and .194's BMC
failed its first power-on call. Each was visible from the outside -- a unit state, a row count, a log line -- long
before anyone looked. Phase 2 (later) wakes the local model on .73 for summaries; .73 sleeps on demand, so the cheap
checks run here on the desktop and the model is woken rarely.

WATCH LIST (data/ops/watch.json, local): a run is registered when it is launched (the step after its completion
waiter, see memory "re-arm needs a waiter"):
    observer.py watch NAME --unit UNIT --progress GLOB [GLOB...] [--total N] [--stall MIN] [--deadline ISO]
                           [--host 194|73] [--log PATH] [--headers K]
CHECKS per watched run, each alert sent ONCE per incident (state in data/ops/observer_state.json):
  ended     the unit left the active state; the log's tail says how (ABORT -> failed, DONE -> finished)
  stall     active, but no new progress rows for --stall minutes (default 45)
  behind    with --total and --deadline: the last hour's row rate will not finish by the deadline
  logline   a new line in --log matching ABORT|Traceback|FAILED|MISMATCH|ERROR
  host      with --host: the host stopped answering ssh for two checks in a row while the run is active
GLOBAL: desktop MemAvailable under 4 GiB (background jobs get killed), /mnt/TG_2TB under 30 GB free.
SINK: the local ntfy topic the desktop already shows (http://127.0.0.1:2586/apollo-monitor; loopback only, so the text
may name files), notify-send if ntfy fails; every alert is also appended to data/ops/observer_events.jsonl.
Alerts are status, never instructions.

USAGE: observer.py check [--dry-run] | status [--line] | watch ... | unwatch NAME   (apollo-observer.timer runs check)"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
OPS = Path(os.environ.get("OBSERVER_OPS", ROOT / "data" / "ops"))
NTFY = os.environ.get("OBSERVER_NTFY", "http://127.0.0.1:2586/apollo-monitor")
BAD = re.compile(r"ABORT|Traceback|FAILED|MISMATCH|ERROR")
HOSTS = {"194": "mark@10.0.0.194", "73": "mark@10.0.0.73"}
MIN_MEM_GIB, MIN_DISK_GB, KEEP_ENDED_H = 4, 30, 24


def paths():
    return OPS / "watch.json", OPS / "observer_state.json", OPS / "observer_events.jsonl"


def load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def save(p, d):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True); tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1)); os.replace(tmp, p)


# --- probes (module functions so the tests can replace them) ---------------------------------------------------------
def unit_state(unit):
    """(ActiveState, Result). A collected transient unit reads inactive with no result."""
    try:
        r = subprocess.run(["systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "Result"], capture_output=True, text=True, timeout=15)
        kv = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
        return kv.get("ActiveState", "unknown"), kv.get("Result", "")
    except Exception as e:
        return "unknown", repr(e)[:80]


def ssh_ok(host):
    try:
        return subprocess.run(["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", HOSTS.get(host, host), "true"], timeout=20).returncode == 0
    except Exception:
        return False


def mem_avail_gib():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"):
            return int(l.split()[1]) / 1048576
    return float("inf")


def disk_free_gb(path="/mnt/TG_2TB"):
    try:
        return shutil.disk_usage(path).free / 1e9
    except Exception:
        return float("inf")


def notify(kind, title, body, prio="default"):
    """Local ntfy first, notify-send if that fails."""
    try:
        req = urllib.request.Request(NTFY, data=body.encode(), headers={"Title": f"Apollo observer: {title}", "Priority": prio,
                                     "Tags": {"high": "rotating_light", "default": "eyes", "low": "white_check_mark"}.get(prio, "eyes")})
        urllib.request.urlopen(req, timeout=10).read(); return "ntfy"
    except Exception:
        try:
            subprocess.run(["notify-send", "-u", "critical" if prio == "high" else "normal", f"Apollo observer: {title}", body], timeout=10,
                           env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}); return "notify-send"
        except Exception:
            return "none"


# --- progress ------------------------------------------------------------------------------------------------------
def count_rows(globs, headers=1):
    """Rows across the files matching the globs (newline count minus `headers` per file), and the newest mtime."""
    n = files = 0; newest = 0.0
    for g in globs:
        for f in glob.glob(g if os.path.isabs(g) else str(ROOT / g)):
            try:
                st = os.stat(f); newest = max(newest, st.st_mtime); files += 1
                with open(f, "rb") as fh:
                    n += sum(c.count(b"\n") for c in iter(lambda: fh.read(1 << 20), b""))
            except OSError:
                continue
    return max(n - headers * files, 0), files, newest


def new_log_lines(path, offset):
    """(lines matching BAD written since offset, new offset). A file that shrank is read again from the start."""
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], offset
    if size < offset: offset = 0
    with open(path, "rb") as f:
        f.seek(offset); chunk = f.read(min(size - offset, 4 << 20))
    return [l.strip()[:300] for l in chunk.decode(errors="replace").splitlines() if BAD.search(l)], offset + len(chunk)


def log_tail_verdict(path):
    try:
        with open(path, "rb") as f:
            f.seek(max(os.path.getsize(path) - 4096, 0)); tail = f.read().decode(errors="replace")
    except OSError:
        return "ended"
    for l in reversed([l for l in tail.splitlines() if l.strip()][-6:]):   # whichever came LAST decides
        if "ABORT" in l: return "failed"
        m = re.search(r"DONE(?:\s*\((\d+)\))?", l)   # our chains end "== DONE (rc)"; Abstend chains end "DONE"
        if m: return "failed" if m.group(1) not in (None, "0") else "finished"
    return "ended"


# --- the check -------------------------------------------------------------------------------------------------------
def check(now=None, dry=False):
    now = now or time.time()
    wp, sp, ep = paths()
    watch, state = load(wp, {}), load(sp, {})
    alerts = []

    def alert(name, kind, title, body, prio="default"):
        alerts.append({"ts": now, "run": name, "kind": kind, "title": title, "body": body, "prio": prio})

    for name, w in watch.items():
        s = state.setdefault(name, {"sent": {}, "samples": [], "offset": 0, "ssh_fail": 0, "was_active": False})
        act, res = unit_state(w["unit"])
        rows, files, newest = count_rows(w.get("progress", []), w.get("headers", 1))
        total = w.get("total")
        s["samples"] = [x for x in s["samples"] if now - x[0] <= 3 * 3600] + [[now, rows]]
        if rows != s.get("rows"):
            s["rows"], s["last_change"] = rows, now; s["sent"].pop("stall", None)
        s.setdefault("last_change", now)
        prog = f"{rows}" + (f"/{total}" if total else "") + " rows"
        if act == "active":
            s["was_active"], s["ended"] = True, None
            idle = (now - s["last_change"]) / 60
            if idle >= w.get("stall_min", 45) and "stall" not in s["sent"]:
                alert(name, "stall", f"{name} stalled", f"No new rows for {idle:.0f} min ({prog}); unit {w['unit']} is still active.", "high")
                s["sent"]["stall"] = now
            hour = [x for x in s["samples"] if now - x[0] <= 3600]
            if total and w.get("deadline") and len(hour) >= 2 and hour[-1][0] > hour[0][0]:
                rate = (hour[-1][1] - hour[0][1]) / ((hour[-1][0] - hour[0][0]) / 3600)
                dl = datetime.fromisoformat(w["deadline"]).timestamp()
                if rate > 0 and now + (total - rows) / rate * 3600 > dl and now - s["sent"].get("behind", 0) > 6 * 3600:
                    eta = datetime.fromtimestamp(now + (total - rows) / rate * 3600).strftime("%m-%d %H:%M")
                    alert(name, "behind", f"{name} behind schedule", f"{prog} at {rate:.0f}/h: ETA {eta}, deadline {w['deadline']}.")
                    s["sent"]["behind"] = now
            if w.get("host"):
                s["ssh_fail"] = 0 if ssh_ok(w["host"]) else s.get("ssh_fail", 0) + 1
                if s["ssh_fail"] >= 2 and "host" not in s["sent"]:
                    alert(name, "host", f".{w['host']} not answering", f"{name} is active but .{w['host']} has failed ssh twice in a row.", "high")
                    s["sent"]["host"] = now
                if s["ssh_fail"] == 0: s["sent"].pop("host", None)
        elif s.get("was_active") and not s.get("ended"):
            verdict = "failed" if res not in ("", "success") else (log_tail_verdict(w["log"]) if w.get("log") else "ended")
            alert(name, "ended", f"{name} {verdict}", f"Unit {w['unit']} is {act}{' (' + res + ')' if res else ''}; {prog}.",
                  "high" if verdict == "failed" else "low")
            s["ended"], s["was_active"] = now, False
        if w.get("log"):
            lines, s["offset"] = new_log_lines(w["log"], s.get("offset", 0))
            seen = set(s.get("seen_lines", []))
            fresh = [l for l in lines if l not in seen]
            if fresh:
                alert(name, "logline", f"{name}: {len(fresh)} error line(s)", "\n".join(fresh[:3]) + ("\n..." if len(fresh) > 3 else ""), "high")
                s["seen_lines"] = (list(seen) + fresh)[-200:]
        s["status"] = {"unit": act, "result": res, "rows": rows, "total": total, "files": files, "newest": newest}

    g = state.setdefault("_global", {"sent": {}})
    for kind, low, msg in (("memory", mem_avail_gib() < MIN_MEM_GIB, f"Desktop MemAvailable under {MIN_MEM_GIB} GiB: background jobs get killed."),
                           ("disk", disk_free_gb() < MIN_DISK_GB, f"/mnt/TG_2TB has under {MIN_DISK_GB} GB free.")):
        if low and kind not in g["sent"]:
            alert("_global", kind, f"desktop {kind} low", msg, "high"); g["sent"][kind] = now
        elif not low:
            g["sent"].pop(kind, None)

    for a in alerts:
        a["via"] = "dry-run" if dry else notify(a["kind"], a["title"], a["body"], a["prio"])
        print(f"ALERT [{a['kind']}] {a['title']}: {a['body'].splitlines()[0] if a['body'] else ''} -> {a['via']}")
    if not dry:
        save(sp, state)
        if alerts:
            ep.parent.mkdir(parents=True, exist_ok=True)
            with open(ep, "a") as f:
                for a in alerts: f.write(json.dumps(a) + "\n")
    return alerts


def status(line=False, now=None):
    now = now or time.time()
    wp, sp, _ = paths(); watch, state = load(wp, {}), load(sp, {})
    out = []
    for name, w in watch.items():
        s = state.get(name, {}); st = s.get("status", {})
        if s.get("ended") and now - s["ended"] > KEEP_ENDED_H * 3600: continue
        hour = [x for x in s.get("samples", []) if now - x[0] <= 3600]
        rate = (hour[-1][1] - hour[0][1]) / ((hour[-1][0] - hour[0][0]) / 3600) if len(hour) >= 2 and hour[-1][0] > hour[0][0] else None
        total = w.get("total"); rows = st.get("rows", "?")
        eta = (datetime.fromtimestamp(now + (total - rows) / rate * 3600).strftime("%m-%d %H:%M")
               if rate and total and isinstance(rows, int) and rows < total else "-")
        idle = f"{(now - s['last_change']) / 60:.0f}m" if s.get("last_change") else "-"
        out.append((name, "ended" if s.get("ended") else st.get("unit", "?"), f"{rows}" + (f"/{total}" if total else ""),
                    f"{rate:.0f}/h" if rate else "-", eta, idle))
    if line:
        return "; ".join(f"{n} {u} {r} {rt} eta {e}" for n, u, r, rt, e, _ in out) if out else "no watched runs"   # labops adds "observer:"
    hdr = ("run", "unit", "rows", "rate", "eta", "idle")
    return "\n".join("  ".join(f"{c:<{w}}" for c, w in zip(r, (24, 9, 12, 8, 12, 6))) for r in [hdr, *out]) if out else "no watched runs"


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    x = sp.add_parser("check"); x.add_argument("--dry-run", action="store_true")
    x = sp.add_parser("status"); x.add_argument("--line", action="store_true")
    x = sp.add_parser("watch"); x.add_argument("name"); x.add_argument("--unit", required=True); x.add_argument("--progress", nargs="+", default=[])
    x.add_argument("--total", type=int); x.add_argument("--stall", type=int, default=45); x.add_argument("--deadline")
    x.add_argument("--host", choices=sorted(HOSTS)); x.add_argument("--log"); x.add_argument("--headers", type=int, default=1)
    sp.add_parser("unwatch").add_argument("name")
    a = ap.parse_args()
    wp, sp_, _ = paths()
    if a.cmd == "check": check(dry=a.dry_run); return
    if a.cmd == "status": print(status(a.line)); return
    watch = load(wp, {})
    if a.cmd == "watch":
        if a.deadline: datetime.fromisoformat(a.deadline)   # fail now, not at check time
        watch[a.name] = {k: v for k, v in {"unit": a.unit, "progress": a.progress, "total": a.total, "stall_min": a.stall, "deadline": a.deadline,
                                           "host": a.host, "log": a.log, "headers": a.headers, "added": time.time()}.items() if v is not None}
        st = load(sp_, {}); st.pop(a.name, None); save(sp_, st)   # a re-registered run starts clean
        save(wp, watch); print(f"watching {a.name}: unit {a.unit}, {len(a.progress)} progress glob(s)")
    elif a.cmd == "unwatch":
        print(f"removed {a.name}" if watch.pop(a.name, None) else f"{a.name} was not watched"); save(wp, watch)


if __name__ == "__main__":
    main()
