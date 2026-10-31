"""PREREG_DRIFT_CAUSE.md Addendum 2. `flips`: writes the two flipped items to a responses file. `answers`: D8, the kwarg on
the answer path, against the server on :8196. `report`: D7, D9 and the size of the date's effect on the judge.
Prints counts and flags only, never item or answer text. Usage: date_judge.py flips|answers|report"""
import json, sys, urllib.request, zlib
AB = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstentionbench/raw/"; ITEMS = "/mnt/TG_2TB/toolchains/AbstentionBench/sub1000_items.jsonl"
OUT = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstend/llama-3.1-8b-instruct/date_judge.json"; FLIP = {("MoralChoiceDataset", "435"), ("WorldSenseDataset", "667")}
L = lambda f: {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(AB + f)) if "error" not in r}


def answers():
    A, B = L("LLAMA8.jsonl"), L("L31AB.jsonl"); items = {(d["dataset"], str(d["index"])): d for d in map(json.loads, open(ITEMS))}
    diff = [k for k in sorted(B) if A[k]["content"] != B[k]["content"]][:5]; hits = 0
    for k in diff:
        b = {"messages": [{"role": "user", "content": items[k]["question"]}], "temperature": 0.8, "top_p": 0.95, "max_tokens": 4000, "cache_prompt": False,
             "seed": (123456789 + zlib.crc32(f"{k[0]}:{k[1]}".encode())) % (2**31), "chat_template_kwargs": {"date_string": "23 Oct 2026"}}
        rq = urllib.request.Request("http://127.0.0.1:8196/v1/chat/completions", json.dumps(b).encode(), {"Content-Type": "application/json"})
        hits += (json.loads(urllib.request.urlopen(rq, timeout=1800).read())["choices"][0]["message"].get("content") or "") == A[k]["content"]
    print("D8 kwarg 23 Oct equals LLAMA8:", hits, "of", len(diff)); json.dump({"D8": [hits, len(diff)]}, open(OUT, "w"))


def report():
    v = lambda f: {k: r.get("verdict") for k, r in L(f).items()}; res = json.load(open(OUT))
    a, b, d24, d28 = v("LLAMA8.judge_norefs.jsonl"), v("L31AB.judge_norefs.jsonl"), v("flip2.d24.jsonl"), v("flip2.d28.jsonl")
    res["D7"] = {"d24_eq_LLAMA8": sum(d24[k] == a[k] for k in FLIP), "d28_eq_L31AB": sum(d28[k] == b[k] for k in FLIP), "d24_ne_d28": sum(d24[k] != d28[k] for k in FLIP)}
    pin, ref = v("L31AB.judge_d28.jsonl"), v("L31AB.judge_dpin.jsonl"); j = L("L31AB.judge_norefs.jsonl")
    res["D9_equal"] = [sum(pin[k] == b[k] for k in b), len(b)]
    def card(x):
        ab = [k for k in x if j[k]["should_abstain"]]; yes = [k for k in x if x[k] is True]
        return {"verdict_yes": len(yes), "recall": round(sum(x[k] is True for k in ab) / len(ab), 4), "none": sum(x[k] is None for k in x)}
    res["date_effect_on_L31AB"] = {"flips_at_26_Jul_2024": sum(ref[k] != b[k] for k in b), "n": len(b), "stored": card(b), "pinned": card(ref)}
    json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "flips":
        with open(AB + "flip2.jsonl", "w") as f:
            for k, r in L("L31AB.jsonl").items():
                if k in FLIP: f.write(json.dumps(r) + "\n")
    elif sys.argv[1] == "answers": answers()
    else: report()
