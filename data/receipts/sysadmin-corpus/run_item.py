#!/usr/bin/env python3
"""Run one sysadmin-corpus item against a model and record the full transcript.

Design notes that matter for the result:
  * The model gets the SYMPTOM and a shell tool. It is not told what is wrong, and never sees
    item.json.
  * Every command is served by replay_shell.py from captured state, so each model and each
    repeat sees byte-identical evidence.
  * Writes incrementally (flush+fsync per turn): per the incremental-persistence rule, a long
    run that dies must not lose everything.
  * Scoring is NOT done here. This produces a transcript; grading is a separate step so the
    same run can be re-graded if the rubric changes.
"""
import json, sys, os, time, urllib.request, argparse
from replay_exec import ExecReplay

SYS = """You are a Linux systems administrator with shell access to a machine that has a problem.

Investigate using the `shell` tool. Run one command at a time and reason about what it tells you.
Do not guess: verify claims against the machine before asserting them.

When you are confident, reply with a final answer containing:
  ROOT CAUSE: <one or two sentences>
  EVIDENCE: <the specific command output that proves it>
  FIX: <the exact remediation>

Reply ONLY with a JSON object each turn, one of:
  {"tool": "shell", "command": "<command>"}
  {"answer": {"root_cause": "...", "evidence": "...", "fix": "..."}}
"""

def call(host, msgs, model=None, timeout=1800, max_tokens=6144, effort="medium"):
    # reasoning_effort is NOT a sampling knob on Qwen3.8 -- the chat template consumes it and
    # prepends literal system text (AFM-23). `medium` injects nothing; `xhigh` injects
    # "validate key assumptions, consider plausible alternatives", which is close to a direct
    # instruction to check premises and therefore contaminates exactly what this corpus measures.
    # It must be an explicit, reported arm -- never an unexamined default.
    body = {"messages": msgs, "max_tokens": max_tokens, "temperature": 0.0,
            "chat_template_kwargs": {"reasoning_effort": effort}}
    if model: body["model"] = model
    r = urllib.request.Request(host.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as f:
        d = json.loads(f.read())
    ch = d["choices"][0]
    m = ch["message"]
    return (m.get("content") or ""), (m.get("reasoning_content") or ""), ch.get("finish_reason")

def extract(text):
    """Model may wrap JSON in prose or fences; find the first balanced object."""
    t = text
    if "</think>" in t: t = t[t.rfind("</think>") + 8:]
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            if t[i] == "{": depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    try: return json.loads(t[start:i+1])
                    except Exception: break
        start = t.find("{", start + 1)
    return None

def main(a):
    item = json.load(open(os.path.join(a.item, "item.json")))
    sh = ExecReplay(os.path.join(a.item, "state"))
    msgs = [{"role": "system", "content": SYS},
            {"role": "user", "content": f"Problem report:\n\n{item['symptom']}\n\nInvestigate."}]
    out = open(a.out, "w")
    def rec(obj):
        out.write(json.dumps(obj) + "\n"); out.flush(); os.fsync(out.fileno())
    rec({"kind": "meta", "item": item["id"], "host": a.host, "rep": a.rep,
         "effort": a.effort, "ts": time.time()})

    answer = None
    for turn in range(a.max_turns):
        try:
            text, reasoning, fin = call(a.host, msgs, a.model, effort=a.effort)
        except Exception as e:
            rec({"kind": "error", "turn": turn, "err": f"{type(e).__name__}: {e}"}); break
        rec({"kind": "raw", "turn": turn, "text": text, "reasoning": reasoning, "finish": fin})
        if not text.strip() and reasoning.strip():
            text = reasoning          # content empty, reasoning present: parse the reasoning
        obj = extract(text)
        if obj is None:
            rec({"kind": "unparsed", "turn": turn})
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": 'Reply with ONLY a JSON object: {"tool":"shell","command":"..."} or {"answer":{...}}'}]
            continue
        if "answer" in obj:
            answer = obj["answer"]; rec({"kind": "answer", "turn": turn, "answer": answer}); break
        cmd = (obj.get("command") or "").strip()
        res = sh.run(cmd)
        rec({"kind": "shell", "turn": turn, "cmd": cmd,
             "matched": sh.log[-1]["matched"], "status": sh.log[-1]["status"],
             "output": res, "src_state": sh.log[-1].get("src_state")})
        msgs += [{"role": "assistant", "content": json.dumps(obj)},
                 {"role": "user", "content": f"$ {cmd}\n{res[:6000]}"}]
    rec({"kind": "final", "answered": answer is not None, "turns_used": turn + 1,
         "commands": [l["cmd"] for l in sh.log],
         "not_captured": [l["cmd"] for l in sh.log if l["status"] == "not_captured"]})
    out.close()
    print(f"{item['id']} rep{a.rep}: answered={answer is not None} turns={turn+1} cmds={len(sh.log)}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("item"); p.add_argument("--host", default="http://127.0.0.1:8099")
    p.add_argument("--model"); p.add_argument("--out", required=True)
    p.add_argument("--rep", type=int, default=1); p.add_argument("--max-turns", type=int, default=25)
    p.add_argument("--effort", default="medium", choices=["low","medium","xhigh"])
    sys.exit(main(p.parse_args()))
