#!/usr/bin/env python3
"""Watch Argus and the agent under test, live. Two local LLMs, one waiting on the other.

Tails the driver's --events stream. No dependencies, no curses -- ANSI only, so it works
over ssh and in a tmux pane next to the run.

The thing worth showing is not the text, it is the BLOCKING RELATIONSHIP: at any instant
exactly one side is doing work and the other is parked. The centre arrow is the point of
the display -- it tells you whether you are waiting on the harness, on the agent's
reasoning, or on a shell command that has gone out to the fake backend.

  ./watch.py                      # follows argus/runs/live.jsonl
  ./watch.py --events other.jsonl
"""
import argparse, json, os, shutil, sys, time
from collections import deque

C = dict(dim="\033[2m", rst="\033[0m", b="\033[1m", cyan="\033[36m", grn="\033[32m",
         yel="\033[33m", red="\033[31m", mag="\033[35m", blu="\033[34m")
VCOL = dict(CORRECT="grn", CLARIFIED="cyan", SUSPECT="yel", WRONG="red", INFRA="mag")
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

def clip(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n-1] + "…"

class State:
    def __init__(self):
        self.scenario = "—"; self.phase = "idle"; self.t0 = time.time()
        self.thoughts = 0; self.tools = 0; self.last_tool = "—"; self.tool_open = False
        self.last_thought = ""; self.usage = "—"; self.verdicts = []
        self.perms = []; self.active = "argus"; self.last_event = time.time()
        self.msg = ""

    def apply(self, e):
        who, kind, d = e["who"], e["kind"], e.get("detail", "")
        self.last_event = e["t"]
        if kind == "scenario":
            self.__init__.__wrapped__ if False else None
            self.scenario, self.phase, self.t0 = d, "connecting", e["t"]
            self.thoughts = self.tools = 0; self.last_tool = "—"; self.last_thought = ""
            self.msg = ""; self.tool_open = False; self.active = "argus"
        elif kind == "prompt":   self.phase, self.active = "prompt sent", "agent"
        elif kind == "thought":  self.thoughts += 1; self.last_thought = d; self.phase = "thinking"; self.active = "agent"
        elif kind == "tool":     self.tools += 1; self.last_tool = d; self.tool_open = True; self.phase = "tool call"; self.active = "tool"
        elif kind == "tool_done":self.tool_open = False; self.phase = "thinking"; self.active = "agent"
        elif kind == "permission": self.perms.append(d); self.phase = "ASKING PERMISSION"; self.active = "argus"
        elif kind == "message":  self.msg += d; self.phase = "replying"; self.active = "agent"
        elif kind == "usage":    self.usage = d
        elif kind == "verdict":
            self.verdicts.append(d); self.phase = "judged"; self.active = "argus"

def render(st, tick):
    w = min(shutil.get_terminal_size((100, 30)).columns, 108)
    half = (w - 7) // 2
    sp = SPIN[tick % len(SPIN)]
    el = time.time() - st.t0
    stale = time.time() - st.last_event
    L, R = [], []

    L.append(f"{C['b']}ARGUS{C['rst']} {C['dim']}harness{C['rst']}")
    L.append(f"scenario  {C['b']}{clip(st.scenario, half-12)}{C['rst']}")
    L.append(f"phase     {clip(st.phase, half-12)}")
    L.append(f"elapsed   {int(el)//60:02d}:{int(el)%60:02d}")
    L.append("")
    L.append(f"{C['dim']}verdicts{C['rst']}")
    for v in st.verdicts[-8:]:
        name, _, verd = v.rpartition(" ")
        L.append(f"  {C[VCOL.get(verd,'dim')]}{verd:<10}{C['rst']}{clip(name, half-14)}")
    if st.perms:
        L.append("")
        L.append(f"{C['yel']}permission captured{C['rst']}")
        for p in st.perms[-2:]:
            L.append(f"  {clip(p, half-4)}")

    R.append(f"{C['b']}AGENT{C['rst']} {C['dim']}hermes · Qwen3.6-27B-MTP @ .73{C['rst']}")
    R.append(f"thoughts  {st.thoughts:<6} tools {st.tools}")
    R.append(f"ctx       {st.usage}")
    R.append(f"last tool {clip(st.last_tool, half-12)}")
    R.append("")
    if st.msg:
        R.append(f"{C['dim']}reply{C['rst']}")
        for ln in (clip(st.msg, half*2)[:half*2][i:i+half-2] for i in range(0, min(len(st.msg), half*2), half-2)):
            R.append(f"  {ln}")
    elif st.last_thought:
        R.append(f"{C['dim']}thinking{C['rst']}")
        t = clip(st.last_thought, (half-2)*3)
        for i in range(0, len(t), half-2):
            R.append(f"  {C['dim']}{t[i:i+half-2]}{C['rst']}")

    n = max(len(L), len(R))
    L += [""] * (n - len(L)); R += [""] * (n - len(R))
    mid = n // 2
    arrow = {"argus": f"{C['cyan']}  ▶{C['rst']}", "agent": f"{C['grn']}{sp} ▶{C['rst']}",
             "tool":  f"{C['yel']}{sp} ⇥{C['rst']}"}[st.active]
    out = [f"\033[H\033[J{C['dim']}argus watch · {'stalled '+str(int(stale))+'s' if stale > 90 else 'live'}{C['rst']}\n"]
    for i in range(n):
        sep = arrow if i == mid else "   "
        lp = L[i] + " " * max(0, half - vislen(L[i]))
        out.append(f"{lp} {sep} {R[i]}")
    who = {"argus": "argus is judging / driving",
           "agent": "argus is BLOCKED — agent is generating",
           "tool":  "agent is BLOCKED — shell command out to fake-google"}[st.active]
    out.append(f"\n{C['dim']}{who}{C['rst']}")
    sys.stdout.write("\n".join(out)); sys.stdout.flush()

def vislen(s):
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            while i < len(s) and s[i] != "m": i += 1
        else: out += 1
        i += 1
    return out

def main(a):
    st = State(); tick = 0; pos = 0
    while True:
        try:
            if os.path.exists(a.events):
                with open(a.events) as f:
                    f.seek(pos)
                    for line in f:
                        line = line.strip()
                        if line:
                            try: st.apply(json.loads(line))
                            except Exception: pass
                    pos = f.tell()
        except Exception: pass
        render(st, tick); tick += 1; time.sleep(0.12)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                     "runs", "live.jsonl"))
    try: main(ap.parse_args())
    except KeyboardInterrupt: print("\033[?25h")
