"""Diagnostic for the pipeline run 2 mismatch: replay 20 diverging + 10 identical sub1000 items on a fresh f74e2fa server,
exactly as run_abench.py sends them (seed, T 0.8, top_p 0.95), twice with neutral penalties and once without. Prints only
equality flags, never item or answer text."""
import json, sys, urllib.request, zlib
AB = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstentionbench/raw/"; ITEMS = "/mnt/TG_2TB/toolchains/AbstentionBench/sub1000_items.jsonl"
H = "http://127.0.0.1:8197/v1/chat/completions"; OUT = sys.argv[1]
NEUTRAL = dict(presence_penalty=0, frequency_penalty=0, repeat_penalty=1, repetition_penalty=1, dry_multiplier=0)
L = lambda f: {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(AB + f)) if "error" not in r}
A, B = L("LLAMA8.jsonl"), L("L31AB.jsonl")
items = {(d["dataset"], str(d["index"])): d for d in map(json.loads, open(ITEMS))}
diff = [k for k in sorted(B) if A[k]["content"] != B[k]["content"]][:20]; same = [k for k in sorted(B) if A[k]["content"] == B[k]["content"]][:10]
def ask(k, neutral):
    body = {"messages": [{"role": "user", "content": items[k]["question"]}], "temperature": 0.8, "top_p": 0.95, "max_tokens": 4000,
            "cache_prompt": False, "seed": (123456789 + zlib.crc32(f"{k[0]}:{k[1]}".encode())) % (2**31)}
    if neutral: body.update(NEUTRAL)
    rq = urllib.request.Request(H, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=1800).read())["choices"][0]["message"].get("content") or ""
rows = []
for k in diff + same:
    n1, n2, p = ask(k, True), ask(k, True), ask(k, False)
    rows.append({"key": k, "group": "diverged" if k in diff else "identical", "n1_eq_n2": n1 == n2, "n1_eq_plain": n1 == p,
                 "n1_eq_L31AB": n1 == B[k]["content"], "n1_eq_LLAMA8": n1 == A[k]["content"], "plain_eq_LLAMA8": p == A[k]["content"]})
json.dump(rows, open(OUT, "w"), indent=1)
for g in ("diverged", "identical"):
    R = [r for r in rows if r["group"] == g]
    print(g, len(R), {f: sum(r[f] for r in R) for f in ("n1_eq_n2", "n1_eq_plain", "n1_eq_L31AB", "n1_eq_LLAMA8", "plain_eq_LLAMA8")})
