#!/usr/bin/env python3
"""PREREG_SPLIT_CONC.md: N parallel 256-token generations (4 distinct fixed prompts), two passes, one row per
(cell, pass, N). Also: gate (count to 20) and ref (first 64 tokens of a fixed prompt, for the tensor-split check).
usage: conc_probe.py URL CELL OUT [gate|ref|run]"""
import concurrent.futures as cf, json, os, re, sys, time, urllib.error, urllib.request
URL, CELL, OUT, MODE = sys.argv[1], sys.argv[2], sys.argv[3], (sys.argv[4] if len(sys.argv) > 4 else "run")
P = ["Explain how a heat pump works, in about 250 words.", "Write a 250-word story about a lighthouse keeper.",
     "Describe the water cycle for a ten-year-old in about 250 words.", "Give a 250-word history of the bicycle."]


def chat(content, n):
    body = json.dumps({"messages": [{"role": "user", "content": content}], "max_tokens": n, "temperature": 0, "seed": 1,
                       "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/v1/chat/completions", body, {"content-type": "application/json"}), timeout=900))
        return {"ok": True, "content": r["choices"][0]["message"].get("content") or "", **(r.get("timings") or {})}
    except urllib.error.HTTPError as e:
        return {"ok": False, "err": f"HTTP {e.code}: {e.read()[:120].decode(errors='replace')}"}
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "err": f"{type(e).__name__}: {e}"}


if MODE == "gate":
    r = chat("Count from 1 to 20, separated by commas.", 96)
    ok = r["ok"] and [int(x) for x in re.findall(r"\d+", r["content"])] == list(range(1, 21))
    print(f"G0 {'PASS' if ok else 'FAIL'} :: {r.get('content', r.get('err'))[:120]!r}"); sys.exit(0 if ok else 1)
if MODE == "ref":
    r = chat(P[0], 64); print(json.dumps({"cell": CELL, "ref": r.get("content", "")})); sys.exit(0 if r["ok"] else 1)
with open(OUT, "a") as f:
    for ps in (1, 2):
        for n in (1, 2, 4):
            t0 = time.time()
            with cf.ThreadPoolExecutor(n) as ex:
                res = list(ex.map(lambda i: chat(P[i], 256), range(n)))
            wall = time.time() - t0
            ok = [r for r in res if r["ok"]]
            row = {"cell": CELL, "pass": ps, "n": n, "ok": len(ok), "fail": n - len(ok), "wall_s": round(wall, 2),
                   "agg_tps": round(sum(r.get("predicted_n", 0) for r in ok) / wall, 2) if ok else 0,
                   "per_stream": [round(r.get("predicted_per_second", 0), 2) for r in ok],
                   "draft_n": sum(r.get("draft_n", 0) or 0 for r in ok), "draft_acc": sum(r.get("draft_n_accepted", 0) or 0 for r in ok),
                   "errs": sorted({r["err"] for r in res if not r["ok"]})[:2]}
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
            print(json.dumps(row), flush=True)
