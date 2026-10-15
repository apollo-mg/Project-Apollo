# bench.py LABEL PORT OUT.jsonl -> greedy, thinking off, cache_prompt false; prose/code/json x 2 reps; fsync per row.
import json, os, sys, time, urllib.request
LABEL, PORT, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
URL = f"http://127.0.0.1:{PORT}"
PROMPTS = {
    "prose": "Write a 200-word paragraph about the history of the bicycle.",
    "code": "Write a Python function that parses an ISO 8601 date string and returns the day of the week. Include a docstring and two doctests. Output only the code.",
    "json": "Return a JSON array of 8 objects describing fictional employees, each with the fields name, age, department, salary and start_date. Output only the JSON.",
}
def chat(content, max_tokens=256):
    body = {"messages": [{"role": "user", "content": content}], "max_tokens": max_tokens, "temperature": 0,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(urllib.request.Request(URL + "/v1/chat/completions", json.dumps(body).encode(),
                   {"Content-Type": "application/json"}), timeout=900).read())
    return time.time() - t0, r
for i in range(300):
    try:
        if urllib.request.urlopen(URL + "/health", timeout=5).status == 200: break
    except Exception: time.sleep(2)
f = open(OUT, "a")
dt, r = chat("Say hello in five words.", 32)
m = r["choices"][0]["message"]
print(f"warmup {dt:.1f}s content={m.get('content')!r}", flush=True)
if not (m.get("content") or "").strip(): print("WARMUP EMPTY"); sys.exit(3)
for kind, p in PROMPTS.items():
    for rep in range(2):
        dt, r = chat(p)
        m = r["choices"][0]["message"]; t = r.get("timings", {})
        row = {"label": LABEL, "kind": kind, "rep": rep, "wall_s": round(dt, 2), "finish": r["choices"][0].get("finish_reason"),
               "content_len": len(m.get("content") or ""), "reasoning_len": len(m.get("reasoning_content") or ""),
               "prompt_n": t.get("prompt_n"), "prompt_tps": t.get("prompt_per_second"), "pred_n": t.get("predicted_n"),
               "pred_tps": t.get("predicted_per_second"), "draft_n": t.get("draft_n"), "draft_acc": t.get("draft_n_accepted"),
               "head": (m.get("content") or "")[:160]}
        f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
        acc = f" draft {row['draft_acc']}/{row['draft_n']}" if row["draft_n"] else ""
        print(f"{kind:5s} r{rep} pred {row['pred_n']} tok @ {row['pred_tps'] or 0:6.2f} tok/s  prompt {row['prompt_tps'] or 0:7.1f} tok/s{acc}  finish={row['finish']} reasoning={row['reasoning_len']}", flush=True)
