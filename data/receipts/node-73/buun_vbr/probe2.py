#!/usr/bin/env python3
"""Probe-only rerun against the ALREADY-RUNNING server (no restart, no 442s reload).

Fixes from run 1: budgets were 320-700 tokens on a thinking model, so every leg died at
the cap inside the reasoning block with empty content. Budget now 3000. Also switches the
throughput source from wall-clock (which included prefill) to the server's own per-request
`eval time` line, and pulls MTP draft-acceptance from the log.
"""
import json, os, re, subprocess, time, urllib.request

BASE = "http://127.0.0.1:8082"
SRV  = os.path.expanduser("~/buun_vbr/server_new.log")
LOG  = os.path.expanduser("~/buun_vbr/probe2.log")

def log(m):
    line = f"[{time.strftime('%F %T')}] {m}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def tail_bytes():
    return os.path.getsize(SRV) if os.path.exists(SRV) else 0

def new_text(off):
    with open(SRV, "r", errors="ignore") as f:
        f.seek(off); return f.read()

def chat(prompt, max_tokens=3000):
    body = json.dumps({"messages":[{"role":"user","content":prompt}],
                       "max_tokens":max_tokens, "temperature":0.0,
                       "stream":False}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    ch = d["choices"][0]["message"]
    return (ch.get("content") or "", ch.get("reasoning_content") or "",
            d.get("usage", {}), time.time()-t0,
            d["choices"][0].get("finish_reason"))

GARBAGE = re.compile(r"(.)\1{40,}|(/ ){15,}")
def coherent(t):
    if not t.strip():            return False, "EMPTY content"
    if GARBAGE.search(t):        return False, "repetition/garbage"
    if len(set(t.split())) < 5:  return False, "vocabulary collapse"
    return True, "ok"

EVAL = re.compile(r"eval time =\s*[\d.]+ ms /\s*(\d+) tokens \(\s*[\d.]+ ms per token,\s*([\d.]+) tokens per second")
DRAFT = re.compile(r"(?:draft acceptance|accept(?:ance)? rate|n_accept)[^0-9]*([\d.]+)", re.I)

PROBES = [
 ("prose",  "Explain in three sentences why memory bandwidth, not FLOPs, usually limits "
            "single-user LLM decode speed."),
 ("count",  "Count from one to forty in words, comma separated. Then say DONE."),
 ("long",   "Write a clear 400-word explanation of what a KV cache is and why its size "
            "matters on consumer GPUs."),
]

def main():
    log("=== probe2: reusing running server, budget 3000 ===")
    results = []
    for name, prompt in PROBES:
        off = tail_bytes()
        try:
            content, reasoning, usage, dt, fin = chat(prompt)
        except Exception as e:
            log(f"{name}: REQUEST FAILED {e}"); continue
        ok, why = coherent(content)
        ct = usage.get("completion_tokens", 0)
        seg = new_text(off)
        evals = EVAL.findall(seg)
        srv_tps = float(evals[-1][1]) if evals else None
        drafts  = DRAFT.findall(seg)
        log(f"{name}: coherent={ok} ({why}) finish={fin} completion_tokens={ct}")
        log(f"    server eval t/s = {srv_tps}  | wall {dt:.1f}s | "
            f"reasoning_chars={len(reasoning)} content_chars={len(content)}")
        if drafts: log(f"    draft stats seen: {drafts[-4:]}")
        log(f"    CONTENT FIRST 300 >>> {content[:300]!r}")
        log(f"    CONTENT LAST  150 >>> {content[-150:]!r}")
        if ok and srv_tps: results.append((name, srv_tps))

    if results:
        best = max(t for _, t in results)
        log(f"SUMMARY: coherent legs {len(results)}/{len(PROBES)} | "
            f"best server-measured {best:.2f} t/s | prior record 22.1-22.3 t/s")
        for n, t in results: log(f"    {n}: {t:.2f} t/s")
    else:
        log("SUMMARY: still no coherent leg — do NOT report throughput")

if __name__ == "__main__":
    main()
