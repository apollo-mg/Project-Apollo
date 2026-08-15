#!/usr/bin/env python3
"""Is speculative decoding actually lossless in practice, and is MTP less so than DFlash?

The showdown's bistability detector compared (draft_n, draft_accepted) only. That
detects variation in the DRAFT PATH, which is not what losslessness claims.
Verify-and-reject guarantees the OUTPUT DISTRIBUTION matches non-speculative
decoding; it says nothing about how many proposals were made along the way.

So a differing draft count with identical text is benign and expected. Differing
TEXT is a real violation. Those were never separated.

This runs the same prompt many times under three conditions and hashes the output:

  off      -- the reference. If this varies, the target itself is nondeterministic
              and nothing else in the test means anything.
  mtp_n3   -- the arm that showed 8/8 of the bistable cells
  dfl_n3   -- the arm that showed zero

Prompt is `code`, which was bistable in mtp_n3 (70.1% vs 71.1%) and bit-identical
in dfl_n3 (227/275 both reps), so it is the cell most likely to separate them.
"""
import hashlib, json, os, sys, time, urllib.request

HOST = os.environ.get("HOST", "http://127.0.0.1:8082")
PROMPT = "Write a Python class LRUCache with get and put, O(1) both. Include docstrings."


def gen(n_predict=320, timeout=900):
    body = {"messages": [{"role": "user", "content": PROMPT}], "temperature": 0,
            "top_k": 1, "seed": 1234, "n_predict": n_predict, "timings_per_token": True}
    req = urllib.request.Request(f"{HOST}/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    m = d["choices"][0].get("message", {})
    text = (m.get("content") or "") + (m.get("reasoning_content") or "")
    t = d.get("timings") or {}
    return {"text": text, "sha": hashlib.sha256(text.encode()).hexdigest()[:16],
            "chars": len(text),
            "tok": (d.get("usage") or {}).get("completion_tokens"),
            "draft_n": t.get("draft_n"), "draft_acc": t.get("draft_n_accepted")}


def main():
    tag  = sys.argv[1]
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rows = []
    for i in range(reps):
        r = gen(); rows.append(r)
        print(f"  {tag:9s} run{i}  sha={r['sha']}  chars={r['chars']:>5}  tok={r['tok']:>4}  "
              f"draft={r['draft_n']}/{r['draft_acc']}", flush=True)
    shas   = {r["sha"] for r in rows}
    drafts = {(r["draft_n"], r["draft_acc"]) for r in rows}
    print(f"  -> {tag}: {len(shas)} distinct OUTPUT(s), {len(drafts)} distinct draft count(s)"
          f"  [{'TEXT STABLE' if len(shas)==1 else '*** TEXT VARIES ***'}]")
    json.dump({"tag": tag, "rows": rows, "distinct_text": len(shas),
               "distinct_draft": len(drafts), "shas": sorted(shas)},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f"lossless_{tag}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
