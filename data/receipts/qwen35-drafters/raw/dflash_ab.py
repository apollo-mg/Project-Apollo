#!/usr/bin/env python3
"""DFlash A/B + n_max depth sweep on Qwen3.5-9B, RX 9070 XT.

Same acceptance instrumentation as headlab_ab.py (timings.draft_n /
draft_n_accepted straight off the server), but with a WIDER PROMPT SET.

Why wider: RESULT_AD_LADDER_HEAD_AUDIT.md Finding 5 recorded that the 5-prompt
headlab bench could not resolve a ~2 pp effect -- prompt type moved acceptance
42.6 %-93.6 % while the variable under test moved it under 5 pp, and one arm was
bistable with a 5.4 pp swing between identical reps. Reps are deterministic
replays and add no information, so the fix is more PROMPTS, not more reps. Reps
are kept at 2 purely to detect that bistability when it happens.

The off-vs-on effect here is large (~3x) and would survive the narrow set; the
n_max sweep is the part that needs the power, since adjacent depths may differ
by only a few points.
"""
import json, os, statistics, sys, time, urllib.request

HOST = os.environ.get("HOST", "http://127.0.0.1:8082")

PROMPTS = [
    # the five canonical ones, kept verbatim so this is comparable to headlab
    ("code",     "Write a Python class LRUCache with get and put, O(1) both. Include docstrings."),
    ("prose",    "Explain how a CPU branch predictor works, in three paragraphs."),
    ("list",     "List the first 30 prime numbers, comma separated."),
    ("repeat",   "Write the numbers 1 to 60, one per line, with no other text."),
    ("reason",   "A tank fills at 4 L/min and drains at 1.5 L/min. It starts at 20 L and holds 200 L. How long until full? Show your work."),
    # additions: spread the acceptance range deliberately, since prompt type is
    # the dominant term and five points do not sample it
    ("json",     "Emit a JSON array of 12 objects, each with keys id, name, score. No prose."),
    ("sql",      "Write a SQL query joining orders, customers and line_items to get revenue per customer per month."),
    ("table",    "Make a markdown table of the 8 planets: name, mass relative to Earth, orbital period."),
    ("translate","Translate into French: 'The compiler emitted a warning about an unused variable in the loop body.'"),
    ("regex",    "Write a regex matching ISO-8601 timestamps with optional timezone, and explain each group."),
    ("story",    "Write the opening 200 words of a story about a lighthouse keeper who finds a radio."),
    ("math",     "Compute the determinant of [[2,1,3],[0,4,1],[5,2,0]] showing cofactor expansion."),
]


def gen(prompt, n_predict=320, timeout=900):
    body = {"messages": [{"role": "user", "content": prompt}], "temperature": 0,
            "top_k": 1, "seed": 1234, "n_predict": n_predict,
            "timings_per_token": True}
    req = urllib.request.Request(f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    dt = time.time() - t0
    u   = d.get("usage", {}) or {}
    tim = d.get("timings") or {}
    tok = u.get("completion_tokens") or 0
    dn, da = tim.get("draft_n"), tim.get("draft_n_accepted")
    return {"tok": tok, "s": round(dt, 2), "tps": round(tok / dt, 2) if dt > 0 else 0,
            "finish": d["choices"][0].get("finish_reason"),
            "draft_n": dn, "draft_accepted": da,
            "accept_rate": round(da / dn, 4) if (dn and da is not None) else None,
            "server_tps": tim.get("predicted_per_second")}


def main():
    tag  = sys.argv[1] if len(sys.argv) > 1 else "arm"
    reps = int(os.environ.get("REPS", "2"))
    out  = []
    for rep in range(reps):
        for name, p in PROMPTS:
            r = gen(p); r.update(prompt=name, rep=rep, arm=tag)
            out.append(r)
            ar = "-" if r["accept_rate"] is None else f"{r['accept_rate']*100:5.1f}%"
            print(f"  {tag:14s} rep{rep} {name:9s} {r['tok']:>4} tok {r['s']:>6.2f}s "
                  f"{r['tps']:>6.2f} t/s  draft {str(r['draft_n']):>5}/{str(r['draft_accepted']):>5} "
                  f"acc {ar}  {r['finish']}", flush=True)

    tps = [r["tps"] for r in out]
    print(f"\n=== {tag}: median {statistics.median(tps):.2f} t/s  mean {statistics.mean(tps):.2f} ===")
    dn = sum(r["draft_n"] or 0 for r in out)
    da = sum(r["draft_accepted"] or 0 for r in out)
    if dn:
        print(f"    draft acceptance {da}/{dn} = {100*da/dn:.2f}%  over {len(out)} responses")
        # per-prompt, because the aggregate hides the spread that dominates it
        for name, _ in PROMPTS:
            g = [r for r in out if r["prompt"] == name and r["draft_n"]]
            if not g: continue
            gdn = sum(r["draft_n"] for r in g); gda = sum(r["draft_accepted"] for r in g)
            reps_seen = {(r["draft_n"], r["draft_accepted"]) for r in g}
            flag = "  <-- BISTABLE across reps" if len(reps_seen) > 1 else ""
            print(f"      {name:9s} {100*gda/gdn:6.2f}%  ({gda}/{gdn}){flag}")
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"dflash_{tag}.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"-> {p}")


if __name__ == "__main__":
    main()
