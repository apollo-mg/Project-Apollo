#!/usr/bin/env python3
"""MTP draft-head A/B across packagers: bartowski Q4_0 head vs unsloth Q6_K head.

Same label (Q6_K), same base model, same node, same flags. The variable is the
8-tensor MTP block that `--spec-type draft-mtp` runs as the draft model.

Captures DRAFT ACCEPTANCE, not just throughput. `timings.draft_n` and
`timings.draft_n_accepted` come straight off the server (server-context.cpp:581,
serialized at server-task.cpp:273). Acceptance is the mechanism -- a worse draft
head shows up there first and shows up in t/s only after it has moved acceptance
far enough to matter. Throughput alone would make a real effect look like noise.
"""
import json, os, statistics, sys, time, urllib.request

HOST = os.environ.get("HOST", "http://127.0.0.1:8082")
PROMPTS = [   # identical to mtp_ab.py so results are comparable to the earlier runs
    ("code",    "Write a Python class LRUCache with get and put, O(1) both. Include docstrings."),
    ("prose",   "Explain how a CPU branch predictor works, in three paragraphs."),
    ("list",    "List the first 30 prime numbers, comma separated."),
    ("repeat",  "Write the numbers 1 to 60, one per line, with no other text."),
    ("reason",  "A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How long until full? Show your work."),
]


def gen(prompt, n_predict=320, timeout=900):
    body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0,
            "top_k": 1, "seed": 1234, "n_predict": n_predict,
            "timings_per_token": True}      # ask for the timings block explicitly
    req = urllib.request.Request(f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    dt = time.time() - t0
    u = d.get("usage", {}) or {}
    tim = d.get("timings") or {}
    tok = u.get("completion_tokens") or 0
    msg = d["choices"][0].get("message", {})
    dn, da = tim.get("draft_n"), tim.get("draft_n_accepted")
    return {"tok": tok, "s": round(dt, 2), "tps": round(tok / dt, 2) if dt > 0 else 0,
            "finish": d["choices"][0].get("finish_reason"),
            "text": msg.get("content") or "",
            "reasoning": msg.get("reasoning_content") or "",
            "draft_n": dn, "draft_accepted": da,
            "accept_rate": round(da / dn, 4) if (dn and da is not None) else None,
            "server_tps": tim.get("predicted_per_second")}


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "arm"
    expect_draft = os.environ.get("EXPECT_DRAFT") == "1"
    reps = int(os.environ.get("REPS", "2"))
    out = []
    for rep in range(reps):
        for name, p in PROMPTS:
            r = gen(p); r.update(prompt=name, rep=rep, arm=tag)
            out.append(r)
            ar = "-" if r["accept_rate"] is None else f"{r['accept_rate']*100:.1f}%"
            print(f"  {tag:12s} rep{rep} {name:7s} {r['tok']:>4} tok {r['s']:>6.2f}s "
                  f"{r['tps']:>6.2f} t/s  draft {str(r['draft_n']):>5}/{str(r['draft_accepted']):>5} "
                  f"acc {ar:>6}  {r['finish']}", flush=True)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"pkg_{tag}.json")
    json.dump(out, open(path, "w"), indent=1)

    tps = [r["tps"] for r in out if r["tok"] > 0]
    print(f"\n=== {tag}: median {statistics.median(tps):.2f} t/s  mean {statistics.mean(tps):.2f} ===")
    drafted = [r for r in out if r["draft_n"]]
    if drafted:
        tot_n = sum(r["draft_n"] for r in drafted)
        tot_a = sum(r["draft_accepted"] for r in drafted)
        print(f"    draft acceptance {tot_a}/{tot_n} = {100*tot_a/tot_n:.2f}%  "
              f"over {len(drafted)}/{len(out)} responses")
        for name, _ in PROMPTS:
            v = [r for r in drafted if r["prompt"] == name]
            if v:
                n = sum(x["draft_n"] for x in v); a = sum(x["draft_accepted"] for x in v)
                print(f"      {name:8s} {100*a/n:5.2f}%  ({a}/{n})")
    # A "MTP on" arm with no draft stats is void, not a null. Fail loudly rather
    # than silently reporting a speedup with no evidence the draft ever ran --
    # this is the same failure mode that voided the Vulkan MoE-cache control.
    if expect_draft and not drafted:
        print(f"\n!!! {tag}: EXPECTED DRAFT STATS AND GOT NONE — arm is VOID", flush=True)
        sys.exit(3)
    print(f"-> {path}")


main()
