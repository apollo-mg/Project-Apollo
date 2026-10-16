# pelican.py OUTDIR REPS -> svgbench pelican protocol on a local server :8091 (TASK, temp 1.0, server-default samplers,
# max_tokens 20000, streamed so reasoning is kept, 480 s generation cap). One json row per rep, fsynced.
import json, os, sys, time, urllib.request
OUT, REPS = sys.argv[1], int(sys.argv[2]); CAP = 480
TASK = "Generate an SVG of a pelican riding a bicycle."
URL = "http://127.0.0.1:8091"
for i in range(300):
    try:
        if urllib.request.urlopen(URL + "/health", timeout=5).status == 200: break
    except Exception: time.sleep(2)
f = open(f"{OUT}/results.jsonl", "a")
for rep in range(1, REPS + 1):
    body = {"model": "x", "temperature": 1.0, "max_tokens": 20000, "stream": True, "stream_options": {"include_usage": True},
            "messages": [{"role": "user", "content": TASK}]}
    req = urllib.request.Request(URL + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time(); content, reasoning, usage, timings, finish, capped = [], [], {}, {}, None, False
    with urllib.request.urlopen(req, timeout=60) as resp:
        for line in resp:
            if time.time() - t0 > CAP: capped = True; break
            line = line.decode().strip()
            if not line.startswith("data:") or line.endswith("[DONE]"): continue
            d = json.loads(line[5:])
            if d.get("usage"): usage = d["usage"]
            if d.get("timings"): timings = d["timings"]
            for c in d.get("choices") or []:
                dl = c.get("delta", {})
                if dl.get("content"): content.append(dl["content"])
                if dl.get("reasoning_content"): reasoning.append(dl["reasoning_content"])
                if c.get("finish_reason"): finish = c["finish_reason"]
    content, reasoning = "".join(content), "".join(reasoning)
    b = f"{OUT}/BOLT_r{rep}"
    open(b + ".content.txt", "w").write(content); open(b + ".reasoning.txt", "w").write(reasoning)
    row = {"rep": rep, "elapsed_s": round(time.time() - t0, 1), "capped": capped, "finish": finish,
           "completion_tokens": usage.get("completion_tokens"), "prompt_tokens": usage.get("prompt_tokens"),
           "reasoning_chars": len(reasoning), "content_chars": len(content), "pred_tps": timings.get("predicted_per_second")}
    f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno()); print(row, flush=True)
