"""Tier-4 metrics 1 and 2: TTFT at depth, and inter-token latency as a DISTRIBUTION.

Closes the one "need" on the tier-4 sheet. Streams the completion and timestamps every
token as it arrives, because a mean hides the thing that actually ruins a session: a model
averaging 30 t/s that stalls 800 ms every twelfth token is not the same product as one
running flat at 28.

GN translation, kept literal:
  average FPS   -> mean t/s
  1 % low FPS   -> throughput implied by the MEAN OF THE SLOWEST 1 % of inter-token gaps
  0.1 % low     -> same, slowest 0.1 %
  frame time    -> inter-token gap, reported in ms at p50 / p90 / p99 / p99.9 / max

Depth arms exist because TTFT at ~0 context is the one case nobody actually runs.

Env: LP_BIN LP_MODEL LP_KV(=q8_0) LP_DEPTHS(=0,2048,16384) LP_NGEN(=384) LP_CTX(=auto)
"""
import json, urllib.request, subprocess, time, os, statistics as st

BIN    = os.environ["LP_BIN"]
MODEL  = os.environ["LP_MODEL"]
KV     = os.environ.get("LP_KV", "q8_0")
DEPTHS = [int(x) for x in os.environ.get("LP_DEPTHS", "0,2048,16384").split(",")]
NGEN   = int(os.environ.get("LP_NGEN", "384"))
CTX    = int(os.environ.get("LP_CTX", str(max(DEPTHS) + NGEN + 1024)))
OUT    = os.environ.get("LP_OUT", "/mnt/TG_2TB/Projects/Apollo/data/receipts/tier4/raw")
os.makedirs(OUT, exist_ok=True)
FILLER = "The quick brown fox jumps over the lazy dog. "

def start(log):
    subprocess.run(["pkill","-x","llama-server"], capture_output=True); time.sleep(8)
    env = dict(os.environ, LD_LIBRARY_PATH=BIN)
    subprocess.Popen([f"{BIN}/llama-server","-m",MODEL,"-ngl","99","-c",str(CTX),
                      "-ctk",KV,"-ctv",KV,"-fa","on","--kv-unified",
                      "--jinja","--host","127.0.0.1","--port","8080"],
                     stdout=open(log,"w"), stderr=subprocess.STDOUT, env=env, start_new_session=True)
    for _ in range(180):
        try: urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2); return True
        except Exception: time.sleep(2)
    return False

def ntok(s):
    r = urllib.request.Request("http://127.0.0.1:8080/tokenize",
        data=json.dumps({"content":s}).encode(), headers={"Content-Type":"application/json"})
    return len(json.loads(urllib.request.urlopen(r, timeout=120).read())["tokens"])

def build(depth):
    if depth == 0: return "Explain how a binary search works."
    p = FILLER
    while ntok(p) < depth: p = p * 2 if ntok(p)*2 < depth else p + FILLER
    return "Read this text, then explain how a binary search works.\n\n" + p

def stream(prompt, n):
    """Returns (ttft_s, [inter-token gaps in s])."""
    body = {"messages":[{"role":"user","content":prompt}], "temperature":0, "top_k":1,
            "n_predict":n, "stream":True}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    t0 = time.perf_counter(); prev = None; ttft = None; gaps = []
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"): continue
            payload = line[5:].strip()
            if payload == "[DONE]": break
            try: d = json.loads(payload)
            except Exception: continue
            delta = (d.get("choices") or [{}])[0].get("delta") or {}
            if not (delta.get("content") or delta.get("reasoning_content")): continue
            now = time.perf_counter()
            if ttft is None: ttft = now - t0
            else: gaps.append(now - prev)
            prev = now
    return ttft, gaps

def low(gaps, frac):
    """GN-style low: throughput implied by the mean of the slowest `frac` of gaps."""
    k = max(1, int(len(gaps) * frac))
    worst = sorted(gaps, reverse=True)[:k]
    return 1.0 / (sum(worst)/len(worst))

print(f"### tier-4 latency profile · KV={KV} · ctx={CTX} · n_predict={NGEN}", flush=True)
print(f"{'depth':>7} {'TTFT s':>8} {'mean t/s':>9} {'1% low':>8} {'0.1% low':>9} "
      f"{'p50 ms':>7} {'p90 ms':>7} {'p99 ms':>7} {'max ms':>8}", flush=True)
rows={}
for d in DEPTHS:
    if not start(f"{OUT}/lp_{KV}_{d}.log"):
        print(f"{d:>7}  server failed to start", flush=True); continue
    p = build(d)
    stream(p, 16)                        # warm the slot; discard
    ttft, gaps = stream(p, NGEN)
    if not gaps:
        print(f"{d:>7}  no tokens streamed", flush=True); continue
    g = sorted(gaps)
    q = lambda f: g[min(len(g)-1, int(len(g)*f))] * 1000
    row = {"ttft_s": round(ttft,3), "mean_tps": round(len(gaps)/sum(gaps),2),
           "low_1pct": round(low(gaps,0.01),2), "low_01pct": round(low(gaps,0.001),2),
           "p50_ms": round(q(.50),2), "p90_ms": round(q(.90),2),
           "p99_ms": round(q(.99),2), "max_ms": round(max(gaps)*1000,2),
           "tokens": len(gaps)+1}
    rows[d]=row
    print(f"{d:>7} {row['ttft_s']:>8.3f} {row['mean_tps']:>9.2f} {row['low_1pct']:>8.2f} "
          f"{row['low_01pct']:>9.2f} {row['p50_ms']:>7.2f} {row['p90_ms']:>7.2f} "
          f"{row['p99_ms']:>7.2f} {row['max_ms']:>8.2f}", flush=True)
subprocess.run(["pkill","-x","llama-server"], capture_output=True)
json.dump(rows, open(f"{OUT}/latency_{KV}.json","w"), indent=2)
print("\n### done", flush=True)
