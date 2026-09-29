#!/usr/bin/env python3
"""PREREG_SWIFT_FLASHNEXT.md helpers against a running server.
  swift_fn_probe.py gate  URL            -> G0 coherence: "Count from 1 to 20": the integers in the reply must be
                                            exactly 1..20 in order, nothing else numeric (exit 1 if not)
  swift_fn_probe.py render URL           -> sha256 of /apply-template for the CAL-xhigh and thinking-off request shapes
  swift_fn_probe.py speed URL ARM MTP OUT -> the 6 fixed prompts of qwen4exp/run_mtp_clock.py, twice, one row each
Speed rows: temp 0, thinking off, 384 tokens, cache_prompt false; flush+fsync per row."""
import hashlib, json, os, re, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qwen4exp"))
from run_mtp_clock import PROMPTS  # noqa: E402  (the verbatim prompt set)


def chat(url, content, n):
    body = {"messages": [{"role": "user", "content": content}], "max_tokens": n, "temperature": 0, "seed": 1,
            "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(), {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=900))


def main():
    mode, url = sys.argv[1], sys.argv[2]
    if mode == "gate":
        r = chat(url, "Count from 1 to 20, separated by commas.", 96)
        got = r["choices"][0]["message"].get("content") or ""
        ok = [int(x) for x in re.findall(r"\d+", got)] == list(range(1, 21))
        print(f"G0 coherence: {'PASS' if ok else 'FAIL'} :: {got[:160]!r}")
        sys.exit(0 if ok else 1)
    if mode == "render":
        q = [{"role": "user", "content": "What is the SI unit of magnetic flux? Answer with the exact term."}]
        hs = []
        for kw in ({"reasoning_effort": "xhigh"}, {"enable_thinking": False}):
            req = urllib.request.Request(url + "/apply-template", json.dumps({"messages": q, "chat_template_kwargs": kw}).encode(),
                                         {"content-type": "application/json"})
            hs.append(hashlib.sha256(json.load(urllib.request.urlopen(req, timeout=60))["prompt"].encode()).hexdigest()[:16])
        print(" ".join(hs))
        return
    arm, mtp, out = sys.argv[3], sys.argv[4], sys.argv[5]
    with open(out, "a") as f:
        for rep in (1, 2):
            for pid, p in PROMPTS:
                t0 = time.time(); r = chat(url, p, 384); tm = r.get("timings") or {}
                row = {"arm": arm, "mtp": mtp, "rep": rep, "prompt": pid, "wall_s": round(time.time() - t0, 3),
                       **{k: tm.get(k) for k in ("predicted_n", "predicted_per_second", "prompt_n", "prompt_per_second",
                                                  "draft_n", "draft_n_accepted")}}
                f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
                acc = f"  acc {row['draft_n_accepted']}/{row['draft_n']}" if row.get("draft_n") else ""
                print(f"{arm} mtp={mtp} rep{rep} {pid:8s} {row['predicted_per_second'] or 0:6.2f} tok/s{acc}", flush=True)


if __name__ == "__main__":
    main()
