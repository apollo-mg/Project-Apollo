#!/usr/bin/env python3
"""Extract a compact event stream from a Claude Code session transcript.

WHY: this session is 198 MB / 82k lines, ~140 MB of which is conversation and most of THAT is
tool OUTPUT. A ledger needs actions, reasons and conclusions -- not the bytes those actions
returned. Dropping tool results is the whole compression.

Emits one line per meaningful event:
  HUMAN  <text>                     what was actually asked
  SAY    <text>                     assistant prose (conclusions, reasoning, corrections)
  TOOL   <name> <arg digest>        what was done
  ERR    <name> <first error line>  what failed

Deliberately NOT emitted: tool_result bodies, file-history snapshots, mode/title/queue records.
Incremental via --since-line so a scheduled run only processes new material.
"""
import argparse, json, os, re, sys

def digest(name, inp, maxlen=160):
    if not isinstance(inp, dict): return ""
    for k in ("command", "file_path", "pattern", "query", "url", "prompt", "description"):
        if k in inp and isinstance(inp[k], str):
            v = " ".join(inp[k].split())
            return f"{k}={v[:maxlen]}"
    return " ".join(f"{k}={str(v)[:40]}" for k, v in list(inp.items())[:2])

def main(a):
    out, n, last = [], 0, 0
    with open(a.transcript, errors="replace") as f:
        for i, line in enumerate(f):
            if i < a.since_line: continue
            last = i
            try: d = json.loads(line)
            except Exception: continue
            t = d.get("type")
            if t not in ("user", "assistant"): continue
            msg = d.get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                if t == "user" and not content.startswith("<"):
                    out.append(f"HUMAN  {' '.join(content.split())[:a.max_text]}")
                continue
            if not isinstance(content, list): continue
            for b in content:
                if not isinstance(b, dict): continue
                bt = b.get("type")
                if bt == "text" and t == "assistant":
                    txt = " ".join((b.get("text") or "").split())
                    if txt: out.append(f"SAY    {txt[:a.max_text]}")
                elif bt == "text" and t == "user":
                    txt = " ".join((b.get("text") or "").split())
                    if txt and not txt.startswith("<"):
                        out.append(f"HUMAN  {txt[:a.max_text]}")
                elif bt == "tool_use":
                    out.append(f"TOOL   {b.get('name','?')}  {digest(b.get('name'), b.get('input'))}")
                elif bt == "tool_result" and b.get("is_error"):
                    c = b.get("content")
                    s = c if isinstance(c, str) else json.dumps(c)
                    out.append(f"ERR    {' '.join(s.split())[:120]}")
            n += 1
    sys.stdout.write("\n".join(out) + "\n")
    if a.state:
        json.dump({"last_line": last}, open(a.state, "w"))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("transcript")
    p.add_argument("--since-line", type=int, default=0)
    p.add_argument("--max-text", type=int, default=600)
    p.add_argument("--state", help="write {last_line} here for incremental runs")
    main(p.parse_args())
