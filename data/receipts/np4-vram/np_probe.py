#!/usr/bin/env python3
"""BACKLOG N16: can .73's daily driver serve N concurrent requests? For N in 1..4: N parallel generations straight to
llama-server (:8080), with both cards' memory.used sampled at 200 ms on the node. One row per (label, N):
successes, HTTP errors, tok/s per stream, and peak / baseline VRAM per card.
usage: np_probe.py LABEL [N ...]   -> appends to rows.jsonl"""
import concurrent.futures as cf, json, os, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

H = "10.0.0.73"; URL = f"http://{H}:8080"
OUT = Path(__file__).resolve().parent / "rows.jsonl"
PROMPTS = ["Explain how a heat pump works, in about 250 words.", "Write a 250-word story about a lighthouse keeper.",
           "Describe the water cycle for a ten-year-old in about 250 words.", "Give a 250-word history of the bicycle."]


def ssh(cmd, timeout=60):
    return subprocess.run(["ssh", "-n", "-o", "BatchMode=yes", H, cmd], capture_output=True, text=True, timeout=timeout).stdout.strip()


def gen(i):
    body = json.dumps({"messages": [{"role": "user", "content": PROMPTS[i]}], "max_tokens": 256, "temperature": 0, "seed": 1,
                       "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(URL + "/v1/chat/completions", body, {"content-type": "application/json"}), timeout=600))
        tm = r.get("timings") or {}
        return {"ok": True, "tps": tm.get("predicted_per_second"), "n": tm.get("predicted_n")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "err": f"HTTP {e.code}: {e.read()[:120].decode(errors='replace')}"}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "err": f"{type(e).__name__}: {e}"}


def mem():
    return [int(x) for x in ssh("timeout 5 nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits").split()]


def main():
    label, ns = sys.argv[1], [int(x) for x in sys.argv[2:]] or [1, 2, 3, 4]
    for n in ns:
        base = mem()
        pid = ssh("nohup nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits -lms 200 > ~/np_mem.csv 2>/dev/null < /dev/null & echo $!")
        t0 = time.time()
        with cf.ThreadPoolExecutor(n) as ex:
            res = list(ex.map(gen, range(n)))
        wall = time.time() - t0
        if ssh(f"cat /proc/{pid}/comm") == "nvidia-smi":
            ssh(f"kill {pid}")
        peak = [0, 0]
        for l in ssh("cat ~/np_mem.csv").splitlines():
            try:
                i, m = [int(x) for x in l.split(",")]; peak[i] = max(peak[i], m)
            except ValueError:
                pass
        ok = [r for r in res if r["ok"]]
        row = {"label": label, "n": n, "ok": len(ok), "fail": n - len(ok), "tps": [round(r["tps"], 2) for r in ok],
               "agg_tps": round(sum(r["n"] for r in ok) / wall, 2) if ok else 0, "base_mib": base, "peak_mib": peak,
               "errs": sorted({r["err"] for r in res if not r["ok"]})[:2]}
        with open(OUT, "a") as f:
            f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
        print(json.dumps(row), flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
