#!/usr/bin/env python3
"""PREREG_IDK_LORA Stage B arm BIAS (no training).

fit:  offline, on the `calib` rows of raw/labels_G41.jsonl. For each b in -4..+12 (step 0.5), an item's answer-first
      first token becomes UNKNOWN when its best UNKNOWN-variant logprob + b beats its best other logprob (top 200).
      Otherwise its unbiased answer-first continuation is graded. Net: +1 CORRECT, -1 WRONG, 0 otherwise. If a negative
      b would turn an unbiased UNKNOWN into an answer we never generated, that item counts -1 (pessimistic; counted in
      the fit table). The b with the highest calib Net is kept (ties: smallest |b|) -> fit_bias.json.
run:  live on M1 against a G41 server: render (thinking off) + "Exact Answer:", /completion greedy, n_predict 48, stop at
      newline, logit_bias b on the three UNKNOWN tokens -> raw/IDK_BIAS.jsonl.

Usage: bias_arm.py fit | bias_arm.py run URL"""
import json, os, sys
from pathlib import Path
import httpx

HERE = Path(__file__).resolve().parent; QA = HERE.parent / "quant-abstention"
sys.path.insert(0, str(QA)); sys.path.insert(0, str(QA.parent / "viability"))
from run_pilot import last_answer, grade   # noqa: E402
PROMPT = json.load(open(QA.parent / "viability" / "fixture_v0_beta.json"))["tier_cal"]["prompt"]
GRID = [x / 2 for x in range(-8, 25)]


def fit():
    rows = [r for r in map(json.loads, open(HERE / "raw" / "labels_G41.jsonl")) if r["split"] == "calib"]
    table = []
    for b in GRID:
        net = flipped_unknown = 0
        for r in rows:
            vids = set(r["var_ids"].values()); top = r["af_top"]
            bv = max((lp for t, lp in top if t in vids), default=None)
            bo = max((lp for t, lp in top if t not in vids), default=None)
            unb_unknown = bv is not None and (bo is None or bv > bo)
            biased_unknown = bv is not None and (bo is None or bv + b > bo)
            if biased_unknown: continue                       # refusal: 0
            if unb_unknown: net -= 1; flipped_unknown += 1; continue
            net += {"CORRECT": 1, "WRONG": -1}.get(r["af_grade"], 0)
        table.append({"b": b, "net": net / len(rows), "pessimistic_flips": flipped_unknown})
    best = max(table, key=lambda t: (round(t["net"], 9), -abs(t["b"])))
    json.dump({"b": best["b"], "calib_net": best["net"], "n_calib": len(rows), "table": table},
              open(HERE / "fit_bias.json", "w"), indent=1)
    print("chosen b", best["b"], "calib Net", round(best["net"], 4), "n", len(rows))


def run(url):
    b = json.load(open(HERE / "fit_bias.json"))["b"]
    c = httpx.Client(timeout=600)
    base = c.post(f"{url}/tokenize", json={"content": "Exact Answer:"}).json()["tokens"]
    vids = [c.post(f"{url}/tokenize", json={"content": "Exact Answer:" + v}).json()["tokens"][len(base):]
            for v in (" UNKNOWN", " Unknown", " unknown")]
    assert all(len(t) == 1 for t in vids); vids = [t[0] for t in vids]
    out = HERE / "raw" / "IDK_BIAS.jsonl"
    done = {json.loads(l)["id"] for l in open(out)} if out.exists() else set()
    with open(out, "a") as f:
        for it in map(json.loads, open(QA / "corpus" / "M1.jsonl")):
            if it["id"] in done: continue
            msgs = [{"role": "user", "content": PROMPT.format(q=it["question"])}]
            P = c.post(f"{url}/apply-template", json={"messages": msgs, "chat_template_kwargs": {"enable_thinking": False}}).json()["prompt"]
            s = c.post(f"{url}/completion", json={"prompt": P + "Exact Answer:", "n_predict": 48, "temperature": 0,
                       "cache_prompt": False, "stop": ["\n"], "logit_bias": [[v, b] for v in vids]}).json()
            af = "Exact Answer:" + s.get("content", "")
            got, _, _ = last_answer(af, "")
            row = {"id": it["id"], "arm": it["arm"], "content": s.get("content", ""), "got": got,
                   "grade": grade(it, got, "stop", af), "b": b}
            f.write(json.dumps(row, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())


if __name__ == "__main__":
    fit() if sys.argv[1] == "fit" else run(sys.argv[2])
