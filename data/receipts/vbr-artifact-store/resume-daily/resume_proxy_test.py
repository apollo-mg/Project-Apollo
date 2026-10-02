#!/usr/bin/env python3
"""--resume on the .73 daily driver, through the wake proxy (10-02). usage: resume_proxy_test.py turn1|turn2 OUT TEXT
turn1: a ~9k-token document + question (a planted fact). turn2: the same history + the answer + a follow-up.
Thinking off, temp 0. Records timings (prompt_n, cache_n) so turn 2 shows whether the prefix came back."""
import json, os, sys, time, urllib.request

MODE, OUT, TEXT = sys.argv[1:4]
URL = "http://localhost:8099/v1/chat/completions"
doc = open(TEXT, encoding="utf-8").read()[100000:136000]
fact = "\n\nNote for the reader: the lighthouse access code is HARBOR 4729.\n\n"
q1 = "Read this document." + fact[:-2] + "\n\n" + doc + "\n\nWhat is the lighthouse access code? Reply with the code only."
state = OUT + ".turn1.json"


def chat(messages):
    body = {"messages": messages, "max_tokens": 32, "temperature": 0, "seed": 1,
            "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    r = json.load(urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(),
                                                                {"content-type": "application/json"}), timeout=1800))
    return r["choices"][0]["message"].get("content") or "", r.get("timings") or {}, round(time.time() - t0, 1)


if MODE == "turn1":
    msgs = [{"role": "user", "content": q1}]
    ans, tm, wall = chat(msgs)
    json.dump({"messages": msgs, "answer": ans}, open(state, "w"))
else:
    st = json.load(open(state))
    msgs = st["messages"] + [{"role": "assistant", "content": st["answer"]},
                             {"role": "user", "content": "Now name two colours, separated by a space, nothing else."}]
    ans, tm, wall = chat(msgs)
row = {"turn": MODE, "wall_s": wall, "answer": ans, "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
       "prompt_ms": tm.get("prompt_ms"), "predicted_n": tm.get("predicted_n")}
with open(OUT, "a") as f:
    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
print(json.dumps(row))
