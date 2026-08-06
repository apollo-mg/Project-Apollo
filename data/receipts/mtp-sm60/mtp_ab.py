#!/usr/bin/env python3
"""MTP speculative-decoding A/B on sm_60 (P100).

Runs a fixed prompt set at temp 0 against one endpoint and records, per prompt:
  - completion tokens, wall time, tok/s
  - the exact output text (for cross-arm agreement)

Speculative decoding is supposed to be DISTRIBUTION-EXACT: at temp 0 the MTP-on and
MTP-off arms must produce identical text. If they don't, MTP is not a pure speed knob
and any A/B that enables it on one arm only is confounded.

Usage: mtp_ab.py <endpoint> <out.json> [n_predict]
"""
import json, urllib.request, sys, time

EP   = sys.argv[1]
OUT  = sys.argv[2]
NTOK = int(sys.argv[3]) if len(sys.argv) > 3 else 512

PROMPTS = [
    "Write a Python function `merge_intervals(intervals)` that merges overlapping intervals. Return only code.",
    "Write a Python function `lru_cache_decorator(maxsize)` implementing an LRU cache decorator from scratch. Return only code.",
    "Write a Python function `topo_sort(graph)` returning a topological ordering, or None if a cycle exists. Return only code.",
    "Explain in one paragraph why quicksort's worst case is O(n^2) and how randomized pivots help.",
    "Write a Python function `binary_search(arr, target)` with correct handling of duplicates, returning the leftmost index. Return only code.",
]

def call(prompt):
    payload = {"messages": [{"role": "user", "content": prompt}],
               "temperature": 0.0, "top_k": 1, "max_tokens": NTOK, "seed": 1234}
    req = urllib.request.Request(EP, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    dt = time.time() - t0
    ch = d["choices"][0]; m = ch["message"]
    usage = d.get("usage", {})
    ct = usage.get("completion_tokens") or 0
    return {"prompt": prompt[:48], "wall_s": round(dt, 2), "completion_tokens": ct,
            "tok_s": round(ct / dt, 2) if dt > 0 else None,
            "finish": ch.get("finish_reason"),
            "content": m.get("content") or "", "rc": m.get("reasoning_content") or ""}

rows = []
for i, p in enumerate(PROMPTS):
    try:
        r = call(p)
    except Exception as e:
        r = {"prompt": p[:48], "error": str(e)}
    rows.append(r)
    print(f"  [{i+1}/{len(PROMPTS)}] {r.get('completion_tokens','ERR')} tok  "
          f"{r.get('wall_s','-')}s  {r.get('tok_s','-')} tok/s  finish={r.get('finish','-')}", flush=True)

ok = [r for r in rows if "error" not in r and r.get("completion_tokens")]
tot_tok = sum(r["completion_tokens"] for r in ok)
tot_s   = sum(r["wall_s"] for r in ok)
summary = {"endpoint": EP, "n_prompts": len(PROMPTS), "n_ok": len(ok),
           "total_completion_tokens": tot_tok, "total_wall_s": round(tot_s, 2),
           "aggregate_tok_s": round(tot_tok / tot_s, 2) if tot_s else None,
           "rows": rows}
json.dump(summary, open(OUT, "w"), indent=2)
print(f"\nAGGREGATE: {tot_tok} tok in {tot_s:.1f}s = {summary['aggregate_tok_s']} tok/s  -> {OUT}")
