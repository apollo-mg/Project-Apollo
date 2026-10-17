#!/usr/bin/env python3
"""PREREG_IDK_LORA: G41 answers every training-pool item (the M1 prompt, greedy, thinking off, max_tokens 256,
cache_prompt false); the unchanged CAL grader marks it. known = CORRECT. Rows -> raw/labels_G41.jsonl (fsynced,
resumable).

For `calib` items it also records the answer-first readout the BIAS arm is fitted on: the thinking-off render plus
`Exact Answer:`, one /completion (greedy, n_predict 48, stop at newline, n_probs 200). The top-200 logprobs of the first
answer token decide, offline, whether a bias b on the three UNKNOWN tokens would make UNKNOWN the greedy first token
(a variant outside the top 200 is treated as never winning: conservative for large b).

Usage: label_pool.py URL"""
import json, os, sys
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(QA)); sys.path.insert(0, str(QA.parent / "viability"))
from run_pilot import last_answer, grade   # noqa: E402  (grading unchanged)
PROMPT = json.load(open(QA.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
VARIANTS = (" UNKNOWN", " Unknown", " unknown")

url = sys.argv[1]; c = httpx.Client(timeout=600)
out = HERE / "raw" / "labels_G41.jsonl"; out.parent.mkdir(exist_ok=True)
done = {json.loads(l)["id"] for l in open(out)} if out.exists() else set()
base = c.post(f"{url}/tokenize", json={"content": "Exact Answer:"}).json()["tokens"]
var_ids = {v: c.post(f"{url}/tokenize", json={"content": "Exact Answer:" + v}).json()["tokens"][len(base):] for v in VARIANTS}
assert all(len(t) == 1 for t in var_ids.values()), var_ids
var_ids = {v: t[0] for v, t in var_ids.items()}
items = [json.loads(l) for l in open(HERE / "train_pool.jsonl")]
with open(out, "a") as f:
    for n, it in enumerate(items):
        if it["id"] in done: continue
        msgs = [{"role": "user", "content": PROMPT.format(q=it["question"])}]
        d = c.post(f"{url}/v1/chat/completions", json={"messages": msgs, "temperature": 0, "max_tokens": 256,
                   "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}).json()
        ch = d["choices"][0]; content = ch["message"].get("content") or ""
        got, _, _ = last_answer(content, ch["message"].get("reasoning_content") or "")
        row = {"id": it["id"], "split": it["split"], "template": it["template"], "gold": it["gold"], "content": content,
               "finish": ch["finish_reason"], "got": got, "grade": grade(it, got, ch["finish_reason"], content),
               "completion_tokens": (d.get("usage") or {}).get("completion_tokens")}
        if it["split"] == "calib":
            P = c.post(f"{url}/apply-template", json={"messages": msgs,
                       "chat_template_kwargs": {"enable_thinking": False}}).json()["prompt"]
            s = c.post(f"{url}/completion", json={"prompt": P + "Exact Answer:", "n_predict": 48, "temperature": 0,
                       "n_probs": 200, "cache_prompt": False, "stop": ["\n"]}).json()
            top = s["completion_probabilities"][0]["top_logprobs"] if s.get("completion_probabilities") else []
            af = "Exact Answer:" + s.get("content", "")
            af_got, _, _ = last_answer(af, "")
            row.update(af_content=s.get("content", ""), af_grade=grade(it, af_got, "stop", af), af_got=af_got,
                       af_top=[(t["id"], t["logprob"]) for t in top], var_ids=var_ids)
        f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        if n % 100 == 0: print(n, it["id"], row["grade"], flush=True)
