#!/usr/bin/env python3
"""Port check: a fixed 60-item M1 slice (20 E, 20 H, 20 U; seed 20261016) through one server, thinking off, greedy, the
instrument's prompt and grader (run_main.py / run_pilot.py, unchanged). Usage: port_slice.py URL TAG -> slice_TAG.jsonl"""
import json, os, random, sys
from pathlib import Path
import httpx
QA = Path(__file__).resolve().parents[2] / "quant-abstention"; sys.path.insert(0, str(QA))
import run_main as RM
URL, TAG = sys.argv[1], sys.argv[2]; OUT = Path(__file__).resolve().parent / f"slice_{TAG}.jsonl"
items = [x for x in map(json.loads, open(QA / "corpus" / "M1.jsonl"))]
rng = random.Random(20261016); sel = []
for g in "EHU": sel += rng.sample(sorted((x for x in items if x["arm"] == g), key=lambda x: x["id"]), 20)
c = httpx.Client(timeout=600); f = open(OUT, "w")
c.post(f"{URL}/v1/chat/completions", json={"messages": [{"role": "user", "content": "Say hello."}], "max_tokens": 16,
       "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}})          # discarded warm-up
for it in sel:
    r = c.post(f"{URL}/v1/chat/completions", json={"messages": [{"role": "user", "content": RM.PROMPT.format(q=it["question"])}],
               "temperature": 0, "max_tokens": 1024, "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}})
    ch = r.json()["choices"][0]; content = ch["message"].get("content") or ""; reasoning = ch["message"].get("reasoning_content") or ""
    got, n, src = RM.last_answer(content, reasoning); g = RM.grade(it, got, ch["finish_reason"], content)
    f.write(json.dumps({"id": it["id"], "grade": g, "got": got, "content": content}, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
print(TAG, "done", len(sel))
