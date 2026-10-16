#!/usr/bin/env python3
"""EXPLORE_THINK_BOLT.md probe: Bolt with thinking ON on a seeded subset of its M1 items; same prompt and grader as run_main.py.
Usage: probe_think_bolt.py URL  -> raw/probe_think_BOLT.jsonl (one row per item, fsynced; resumable)."""
import json, os, random, sys
from pathlib import Path
import httpx
HERE = Path(__file__).resolve().parent
import run_main as RM                                   # PROMPT and the grading helpers, unchanged
URL = sys.argv[1]; OUT = HERE / "raw" / "probe_think_BOLT.jsonl"
items = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}
base = {r["id"]: r for r in map(json.loads, open(HERE / "raw" / "main_BOLT.jsonl")) if "id" in r}
rng = random.Random(20261016)
pick = lambda g, grade, n: rng.sample(sorted(i for i, r in base.items() if items[i]["arm"] == g and r["grade"] == grade), n)
sel = [("U_wrong", i) for i in pick("U", "WRONG", 20)] + [("H_correct", i) for i in pick("H", "CORRECT", 5)] + \
      [("U_refused", i) for i in pick("U", "ABSTAINED", 5)]
done = set()
if OUT.exists(): done = {json.loads(l)["id"] for l in open(OUT)}
c = httpx.Client(timeout=1800)
with open(OUT, "a") as f:
    for cls, i in sel:
        if i in done: continue
        it = items[i]
        r = c.post(f"{URL}/v1/chat/completions", json={"messages": [{"role": "user", "content": RM.PROMPT.format(q=it["question"])}],
                   "temperature": 0, "max_tokens": 8192, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": True}})
        r.raise_for_status(); ch = r.json()["choices"][0]; u = r.json().get("usage", {})
        content, reasoning, fin = ch["message"].get("content") or "", ch["message"].get("reasoning_content") or "", ch["finish_reason"]
        got, nmatch, src = RM.last_answer(content, reasoning)
        g = RM.grade(it, got, fin, content)
        row = {"id": i, "class": cls, "grade_off": base[i]["grade"], "grade_on": g, "got_off": base[i]["got"], "got_on": got,
               "finish": fin, "answer_src": src, "completion_tokens": u.get("completion_tokens"), "reasoning_chars": len(reasoning),
               "content": content, "reasoning": reasoning}
        f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        print(f"{cls:9s} {i}  off={base[i]['grade']:9s} on={g:9s} tok={u.get('completion_tokens')}  got_on={str(got)[:40]!r}", flush=True)
