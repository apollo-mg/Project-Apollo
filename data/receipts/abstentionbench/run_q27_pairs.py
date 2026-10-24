#!/usr/bin/env python3
"""PREREG_ABSTENTIONBENCH Addendum 2: Qwen3.8-27B thinking OFF vs ON, interleaved per item in a seeded random order, so
both arms see the same server state and a run stopped at the registered deadline leaves a random sample of pairs.
OFF: /v1/chat/completions, chat_template_kwargs {"enable_thinking": false}, max_tokens 4000 (as run_abench.py).
ON:  two-phase budget forcing as Meta's VLLMReasoningChatModelBase (as run_abench_think.py): reasoning up to 4000 tokens
     (stop at </think>, or cut and closed), then the answer up to 4000 tokens; reasoning_effort "medium" (the only value
     that injects no system text). No "Final Answer: " prefix on the judged text.
Both: temperature 0.8, top_p 0.95, no system prompt, cache_prompt false, per-item seed as run_abench.py (ON phase 2 uses
seed + 1). Requests carry x-apollo-guest so the wake proxy keeps Hermes's warm-up head. One JSON line per item and arm,
flushed + fsynced; resumes, retrying errored rows. Stops cleanly at --deadline (local time, ISO).
Usage: run_q27_pairs.py --items fast_subset.jsonl --off raw/Q27OFF.jsonl --on raw/Q27ON.jsonl --proxy URL --node URL
       --deadline 2026-10-26T12:00 [--expect-model FILE] [--order-seed N]"""
import argparse, datetime, json, os, random, time, urllib.request, zlib
ap = argparse.ArgumentParser()
for k in ("--items", "--off", "--on", "--proxy", "--node", "--deadline"): ap.add_argument(k, required=True)
ap.add_argument("--expect-model"); ap.add_argument("--order-seed", type=int, default=20261024)
ap.add_argument("--seed-base", type=int, default=123456789); ap.add_argument("--timeout", type=int, default=3600)
ap.add_argument("--attempts", type=int, default=3)
a = ap.parse_args()
deadline = datetime.datetime.fromisoformat(a.deadline)
G = {"temperature": 0.8, "top_p": 0.95, "cache_prompt": False}; GUEST = {"x-apollo-guest": "1"}
def post(url, body, hdr=None):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(hdr or {})})
    return json.loads(urllib.request.urlopen(req, timeout=a.timeout).read())
def props():
    return json.loads(urllib.request.urlopen(a.proxy.rstrip("/") + "/props", timeout=300).read())   # wakes the node
if a.expect_model and not props()["model_path"].endswith(a.expect_model): raise SystemExit("unexpected model at the proxy")
def done(path):
    s = set()
    if os.path.exists(path):
        for l in open(path):
            r = json.loads(l)
            if "error" not in r: s.add((r["dataset"], r["index"]))
    return s
def off(it, seed):
    d = post(a.proxy.rstrip("/") + "/v1/chat/completions", {"messages": [{"role": "user", "content": it["question"]}], "max_tokens": 4000,
             "seed": seed, "chat_template_kwargs": {"enable_thinking": False}, **G}, GUEST)
    ch = d["choices"][0]; m = ch["message"]
    return dict(content=m.get("content") or "", reasoning=m.get("reasoning_content") or "", finish=ch.get("finish_reason"), usage=d.get("usage", {}))
def on(it, seed):
    prompt = post(a.node.rstrip("/") + "/apply-template", {"messages": [{"role": "user", "content": it["question"]}],
                  "chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "medium"}})["prompt"]
    if not prompt.endswith("<think>\n") or "<|im_start|>system" in prompt: raise RuntimeError(f"unexpected template tail {prompt[-40:]!r}")
    d1 = post(a.proxy.rstrip("/") + "/v1/completions", {"prompt": prompt, "max_tokens": 4000, "stop": ["</think>"], "seed": seed, **G}, GUEST)
    c1 = d1["choices"][0]; reasoning = c1["text"]
    d2 = post(a.proxy.rstrip("/") + "/v1/completions", {"prompt": prompt + reasoning.rstrip("\n") + "\n</think>\n\n", "max_tokens": 4000,
              "stop": ["<|im_end|>", "<|im_start|>"], "seed": seed + 1, **G}, GUEST)
    c2 = d2["choices"][0]; answer = c2["text"]
    if "</think>" in answer:
        parts = answer.split("</think>"); reasoning += "".join(parts[:-1]); answer = parts[-1]
    return dict(content=answer.strip(), reasoning=reasoning, forced=c1.get("finish_reason") == "length", finish1=c1.get("finish_reason"),
                finish=c2.get("finish_reason"), usage1=d1.get("usage", {}), usage=d2.get("usage", {}))
items = [json.loads(l) for l in open(a.items)]
items.sort(key=lambda r: (r["dataset"], r["index"])); random.Random(a.order_seed).shuffle(items)
D = {"off": done(a.off), "on": done(a.on)}; F = {"off": open(a.off, "a"), "on": open(a.on, "a")}
for n, it in enumerate(items):
    if datetime.datetime.now() >= deadline: print(f"deadline reached after {n} items in order"); break
    key = (it["dataset"], it["index"]); seed = (a.seed_base + zlib.crc32(f"{key[0]}:{key[1]}".encode())) % (2**31)
    for arm, fn in (("off", off), ("on", on)):
        if key in D[arm]: continue
        rec = {"dataset": key[0], "index": key[1], "order": n}; t0 = time.time()
        for attempt in range(a.attempts):
            try:
                props(); rec.update(fn(it, seed)); rec.pop("error", None); break
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {str(e)[:200]}"; time.sleep(20 * (attempt + 1))
        rec["s"] = round(time.time() - t0, 2)
        F[arm].write(json.dumps(rec) + "\n"); F[arm].flush(); os.fsync(F[arm].fileno())
else:
    print("all items done")
