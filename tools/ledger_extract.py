#!/usr/bin/env python3
"""Extract a compact event stream from a Claude Code session transcript.

WHY: this session is 198 MB / 82k lines, ~140 MB of which is conversation and most of THAT is
tool OUTPUT. A ledger needs actions, reasons and conclusions -- not the bytes those actions
returned. Dropping tool results is the whole compression.

Emits one line per meaningful event:
  HUMAN  <text>                     what was actually asked
  SAY    <text>                     assistant prose (conclusions, reasoning, corrections)
  TOOL   <name> <arg digest>        what was done
  ERR    [<class>] <tool>(<command digest>): <error text>   what failed
         class FAIL      = a real failure (traceback, error message, abort, ...)
         class NONZERO   = a search/compare command (grep, find, test, diff, ...) exited non-zero;
                           usually means "no match", NOT that anything broke
         class EXIT      = some other command exited non-zero with no error text

Deliberately NOT emitted: tool_result bodies, file-history snapshots, mode/title/queue records.
Incremental via --since-line so a scheduled run only processes new material.
"""
import argparse, json, os, re, sys

# 2026-09-24: an ERR used to be the first 120 chars of any is_error tool_result, with no link to the
# command that produced it. A `grep` that exited 1 (no match in its last file) therefore became
# "ERR Exit code 1 argus/driver.py:9: ...route that exists in no Hermes codebase", and the diary
# model turned that into an invented cause-and-effect story. Each ERR now names its command and a
# class, so a search that found nothing cannot read as a failure.
ERROR_SIG = re.compile(r"(?i)(traceback|\berror\b|exception|abort|fatal|failed|denied|not found|"
                       r"no such file|segfault|out of memory|killed|timed? ?out|cannot|refused|invalid)")
# commands whose non-zero exit normally means "nothing matched / differs / absent", not "broke"
SEARCHY = re.compile(r"^(\S*/)?(grep|rg|egrep|fgrep|find|test|\[|\[\[|diff|cmp|pgrep|which|type|"
                     r"command\s+-v|git\s+(diff|grep|check-ignore|ls-files))\b")

def last_command(cmd):
    """The exit status of a compound command is its LAST command's: take the final segment."""
    segs = [x.strip() for x in re.split(r"(?:&&|\|\||;|\n|\|)", cmd or "") if x.strip()]
    last = segs[-1] if segs else ""
    last = re.sub(r"^(timeout\s+\S+\s+|sudo\s+|env\s+(\S+=\S+\s+)*|!\s*)", "", last)
    return re.sub(r"^ssh\s+(-\S+\s+(\S+\s+)?)*\S+@?\S*\s+['\"]?", "", last)

def classify_err(text, cmd):
    if SEARCHY.search(last_command(cmd)):
        return "NONZERO"
    if re.match(r"^Exit code 124\b", text.strip()) or "<tool_use_error>" in text:
        return "FAIL"                      # timeout, or the harness refused the call
    body = re.sub(r"^Exit code \d+\s*", "", text.strip())
    return "FAIL" if ERROR_SIG.search(body[:400]) else "EXIT"

def content_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
    return json.dumps(c)

def digest(name, inp, maxlen=160):
    if not isinstance(inp, dict): return ""
    for k in ("command", "file_path", "pattern", "query", "url", "prompt", "description"):
        if k in inp and isinstance(inp[k], str):
            v = " ".join(inp[k].split())
            return f"{k}={v[:maxlen]}"
    return " ".join(f"{k}={str(v)[:40]}" for k, v in list(inp.items())[:2])

def main(a):
    out, n, last = [], 0, 0
    uses = {}   # tool_use_id -> (name, digest, raw command)
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
                    dg = digest(b.get('name'), b.get('input'))
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    uses[b.get("id")] = (b.get('name', '?'), dg, str(inp.get("command", "")))
                    out.append(f"TOOL   {b.get('name','?')}  {dg}")
                elif bt == "tool_result" and b.get("is_error"):
                    s = content_text(b.get("content"))
                    name, dg, cmd = uses.get(b.get("tool_use_id"), ("?", "", ""))
                    cls = classify_err(s, cmd)
                    ctx = f"{name}({' '.join(dg.split())[:70]})"
                    out.append(f"ERR    [{cls}] {ctx}: {' '.join(s.split())[:120]}")
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
