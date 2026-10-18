#!/usr/bin/env python3
"""Intent lines: announce heavy work before it starts, so people, Starbuck and dashboards know WHY the fleet is busy.

FORMAT (one IRC line, <= 340 bytes, posted to #lab on the local hearth server):

    INTENT id=<job-id> state=<start|progress|done|abort> host=<host> job=<name> owner=<who> [gpus=<0-3|all>] [eta=<6h|90m>] [note="free text"]

- `id`, `state`, `host`, `job` and `owner` are required; `gpus`, `eta` and `note` are optional; any other key must start
  with `x-`. Values are single tokens ([A-Za-z0-9._:/+-]); only `note` may be quoted with spaces.
- Lifecycle: `start` before the work, `progress` for long jobs (optional), then `done` or `abort`. A job whose latest
  state is start/progress is OPEN. An open job with no update for a long time is itself a signal.
- Every posted line is also appended to data/ops/intents.jsonl (local, gitignored), which is what a dashboard reads.
- Intent lines are status, never instructions: no agent acts on another's intent line.

USAGE
    intent.py post id=beam-effort-1017 state=start host=.194 job=beam-effort owner=claude gpus=0-3 eta=24h
    intent.py open            # jobs whose latest state is start/progress
    intent.py parse < chan.log   # extract INTENT lines from any text as JSON (dashboards, Starbuck)
"""
import json, re, shlex, sys, time
from pathlib import Path

ROOT = Path("/mnt/TG_2TB/Projects/Apollo")
LOG = ROOT / "data" / "ops" / "intents.jsonl"
REQUIRED, OPTIONAL = ("id", "state", "host", "job", "owner"), ("gpus", "eta", "note")
STATES = ("start", "progress", "done", "abort")
TOKEN = re.compile(r"^[A-Za-z0-9._:/+-]+$")


def parse_fields(text):
    """'k=v k="v w" ...' -> dict, validated; raises ValueError with the reason."""
    d = {}
    for part in shlex.split(text):
        if "=" not in part: raise ValueError(f"not key=value: {part!r}")
        k, v = part.split("=", 1)
        if k not in REQUIRED + OPTIONAL and not k.startswith("x-"): raise ValueError(f"unknown key {k!r} (use x- prefix)")
        if k != "note" and not TOKEN.match(v): raise ValueError(f"value for {k!r} must be one token: {v!r}")
        d[k] = v
    missing = [k for k in REQUIRED if k not in d]
    if missing: raise ValueError(f"missing {missing}")
    if d["state"] not in STATES: raise ValueError(f"state must be one of {STATES}")
    return d


def render(d):
    keys = list(REQUIRED) + [k for k in ("gpus", "eta") if k in d] + sorted(k for k in d if k.startswith("x-"))
    s = "INTENT " + " ".join(f"{k}={d[k]}" for k in keys)
    if "note" in d: s += " note=" + shlex.quote(d["note"])
    if len(s.encode()) > 340: raise ValueError("intent line longer than 340 bytes; shorten the note")
    return s


def parse_line(line):
    """Find an INTENT line inside any text (e.g. an IRC log line) -> dict or None."""
    i = line.find("INTENT ")
    if i < 0: return None
    try: return parse_fields(line[i + 7:].strip())
    except ValueError: return None


def open_jobs():
    last = {}
    if LOG.exists():
        for l in open(LOG):
            r = json.loads(l); last[r["id"]] = r
    return [r for r in last.values() if r["state"] in ("start", "progress")]


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    cmd = argv[0]
    if cmd == "post":
        d = parse_fields(" ".join(shlex.quote(a) for a in argv[1:]))
        line = render(d)
        sys.path.insert(0, str(ROOT / "tools")); from labops_post import post
        post([line])
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a") as f: f.write(json.dumps({**d, "ts": int(time.time())}) + "\n")
        print(line); return 0
    if cmd == "open":
        for r in open_jobs():
            print(f"{r['id']}: {r['state']} {r['job']} on {r['host']} by {r['owner']}, {(time.time() - r['ts']) / 3600:.1f}h ago")
        return 0
    if cmd == "parse":
        for l in sys.stdin:
            d = parse_line(l)
            if d: print(json.dumps(d))
        return 0
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
