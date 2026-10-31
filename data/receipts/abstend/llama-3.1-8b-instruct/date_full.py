"""PREREG_DRIFT_CAUSE.md Addendum 3. `resid`: writes the items pass 1 did not reproduce. `merge`: builds LLAMA8R from both passes.
`report`: D10 and D11. Prints counts only, never item or answer text. Usage: date_full.py resid|merge|report"""
import json, sys
AB = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstentionbench/raw/"; ITEMS = "/mnt/TG_2TB/toolchains/AbstentionBench/sub1000_items.jsonl"
OUT = "/mnt/TG_2TB/Projects/Apollo/data/receipts/abstend/llama-3.1-8b-instruct/date_full.json"
L = lambda f: {(r["dataset"], str(r["index"])): r for r in map(json.loads, open(AB + f)) if "error" not in r}
same = lambda x, y: x["content"] == y["content"] and x["finish"] == y["finish"]


def resid():
    A, P = L("LLAMA8.jsonl"), L("LLAMA8R23.jsonl"); keep = {k for k in P if not same(A[k], P[k])}
    with open(AB + "LLAMA8R_resid_items.jsonl", "w") as f:
        for l in open(ITEMS):
            d = json.loads(l)
            if (d["dataset"], str(d["index"])) in keep: f.write(l)
    print("pass 1 equal", len(P) - len(keep), "of", len(P), "| residual", len(keep))


def merge():
    A, P, Q = L("LLAMA8.jsonl"), L("LLAMA8R23.jsonl"), L("LLAMA8R24.jsonl")
    with open(AB + "LLAMA8R.jsonl", "w") as f:
        for k, r in P.items():
            f.write(json.dumps(Q[k] if k in Q and same(A[k], Q[k]) else r) + "\n")


def report():
    A, P, Q, M = L("LLAMA8.jsonl"), L("LLAMA8R23.jsonl"), L("LLAMA8R24.jsonl"), L("LLAMA8R.jsonl")
    order = {}
    for i, l in enumerate(open(AB + "LLAMA8.jsonl")):
        r = json.loads(l); order[(r["dataset"], str(r["index"]))] = i
    only23 = [order[k] for k in P if same(A[k], P[k]) and k in Q and not same(A[k], Q[k])]
    need24 = [order[k] for k in Q if same(A[k], Q[k]) and not same(A[k], P[k])]
    # pass 2 only ran the residual, so "needed 23" is read from the 20 + 15 rows of date_replay: there, d23 true and d24 false
    rep = json.load(open(AB.replace("abstentionbench/raw/", "abstend/llama-3.1-8b-instruct/date_replay.json")))["rows"]
    d23 = [order[tuple(r["key"])] for r in rep if r.get("d23_eq_LLAMA8") and not r.get("d24_eq_LLAMA8")]
    res = {"D10_equal": [sum(same(A[k], M[k]) for k in M), len(M)], "pass1_equal": sum(same(A[k], P[k]) for k in P), "residual": len(Q), "needed_24": len(need24),
           "still_differ": sum(not same(A[k], M[k]) for k in M), "file_rows": len(order),
           "D11": {"last_row_needing_23_from_replay": max(d23, default=None), "first_row_needing_24": min(need24, default=None), "n_needing_24": len(need24)}}
    if d23 and need24: res["D11"]["held"] = max(d23) < min(need24)
    json.dump(res, open(OUT, "w"), indent=1); print(json.dumps(res, indent=1))


def tail_items():   # Addendum 4: sub1000 rows after midnight that pass 2 did not run
    Q = L("LLAMA8R24.jsonl"); order = {(r["dataset"], str(r["index"])): i for i, r in enumerate(map(json.loads, open(AB + "LLAMA8.jsonl")))}; n = 0
    with open(AB + "LLAMA8R_tail_items.jsonl", "w") as f:
        for l in open(ITEMS):
            d = json.loads(l); k = (d["dataset"], str(d["index"]))
            if order[k] >= 1474 and k not in Q: f.write(l); n += 1
    print("tail items", n)


def tail_report():
    A, T = L("LLAMA8.jsonl"), L("LLAMA8R24b.jsonl"); res = {"D13_equal": [sum(same(A[k], T[k]) for k in T), len(T)], "midnight_row_by_timing": 1472, "first_row_needing_24": 1474}
    json.dump(res, open(OUT.replace("date_full", "date_tail"), "w"), indent=1); print(json.dumps(res))


if __name__ == "__main__":
    {"resid": resid, "merge": merge, "report": report, "tail-items": tail_items, "tail-report": tail_report}[sys.argv[1]]()
