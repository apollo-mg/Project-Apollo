#!/usr/bin/env python3
"""Brevity probe: same 40 prompts x 2 seeds against a llama-server with thinking ON.
Writes JSONL rows: {idx, seed, think_tokens, answer_tokens, finish, has_think}.
Usage: gen_brevity.py <out.jsonl>"""
import json
import sys
import threading
import urllib.request

PORT = 8090
OUT = sys.argv[1]
SEEDS = [11, 22]

PROMPTS = [
    "Explain how a hash map handles collisions, with the trade-offs of each strategy.",
    "Write a Python function that merges overlapping intervals, with tests.",
    "What actually causes inflation? Walk through the main mechanisms.",
    "Draft a short story opening about a lighthouse keeper who finds a message in a bottle.",
    "Compare TCP and UDP for a multiplayer game — which would you pick and why?",
    "Explain photosynthesis to a curious 12-year-old.",
    "Write a bash script that backs up a directory, keeping the last 7 daily snapshots.",
    "What were the main causes of the fall of the Western Roman Empire?",
    "Explain the difference between processes and threads, including when each is preferable.",
    "Write a SQL query to find the second-highest salary per department, and explain it.",
    "How does a refrigerator work? Explain the thermodynamic cycle.",
    "Draft a polite email declining a job offer while keeping the relationship warm.",
    "Explain gradient descent and why learning rates matter.",
    "Write a C function that reverses a singly linked list iteratively.",
    "What is the Monty Hall problem and why do people get it wrong?",
    "Describe the plot structure of a classic three-act screenplay.",
    "Explain DNS resolution step by step, from typing a URL to getting an IP.",
    "Write a haiku sequence (three haiku) about winter in a city.",
    "What are the trade-offs between microservices and a monolith for a small team?",
    "Explain how vaccines train the immune system.",
    "Write a JavaScript debounce function and explain when to use it vs throttle.",
    "Summarize the key ideas of stoic philosophy and how people apply them today.",
    "Explain why the sky is blue and sunsets are red.",
    "Write a Dockerfile for a Python web app with sensible layer caching.",
    "What is quantitative easing and what are its risks?",
    "Describe how to knead and proof bread dough, for a first-time baker.",
    "Explain big-O notation with three concrete examples.",
    "Write a regex that validates an email address and explain its parts.",
    "What happened during the Cuban Missile Crisis, day by day, briefly?",
    "Explain the CAP theorem with a practical example of each trade-off.",
    "Write a short dialogue between a detective and a suspect who talks too much.",
    "How do noise-cancelling headphones work?",
    "Explain Rust's ownership model to a C programmer.",
    "Draft a README introduction for an open-source CLI tool that renames photos by EXIF date.",
    "What are Lagrange points and why are they useful for spacecraft?",
    "Write a Python generator that yields primes lazily, and explain its memory behavior.",
    "Explain the difference between symmetric and asymmetric encryption with use cases.",
    "Describe a good strategy for the first ten moves of a chess game, for a beginner.",
    "Explain how compilers use intermediate representations, briefly.",
    "Write a short product announcement for a fictional e-ink tablet aimed at writers.",
]


def post(path, obj, timeout=2400):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def ntok(text):
    if not text:
        return 0
    return len(post("/tokenize", {"content": text}, timeout=120).get("tokens", []))


def one(idx, seed):
    resp = post("/v1/chat/completions", {
        "messages": [{"role": "user", "content": PROMPTS[idx]}],
        "temperature": 0.7, "top_p": 0.95, "min_p": 0.05,
        "max_tokens": 3072, "seed": seed,
        "chat_template_kwargs": {"enable_thinking": True},
    })
    ch = resp["choices"][0]
    msg = ch["message"]
    think = msg.get("reasoning_content") or ""
    content = msg.get("content") or ""
    if not think and "<think>" in content:
        import re
        m = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
        if m:
            think = m.group(1)
            content = content[m.end():]
    return {
        "idx": idx, "seed": seed,
        "think_tokens": ntok(think), "answer_tokens": ntok(content),
        "finish": ch.get("finish_reason"), "has_think": bool(think),
    }


jobs = [(i, s) for i in range(len(PROMPTS)) for s in SEEDS]
results = [None] * len(jobs)
lock = threading.Lock()
cursor = [0]


def worker():
    while True:
        with lock:
            if cursor[0] >= len(jobs):
                return
            j = cursor[0]
            cursor[0] += 1
        i, s = jobs[j]
        try:
            results[j] = one(i, s)
        except Exception as e:  # noqa: BLE001
            results[j] = {"idx": i, "seed": s, "error": str(e)}
        print(f"done {j+1}/{len(jobs)} idx={i} seed={s}", flush=True)


threads = [threading.Thread(target=worker) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()

with open(OUT, "w") as f:
    for r in results:
        f.write(json.dumps(r) + "\n")
errs = sum(1 for r in results if r and "error" in r)
print(f"WROTE {OUT}  rows={len(results)}  errors={errs}")
