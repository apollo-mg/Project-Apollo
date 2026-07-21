#!/usr/bin/env python3
"""Restart .73's llama-server on the freshly built binary using its EXACT current argv,
then probe. Coherence is checked BEFORE throughput is reported — the "/"-spam incident
proved a t/s number without reading the output text is worthless.

Leaves the server running for Hermes. Argv is captured from /proc so the JSON
--chat-template-kwargs and paths with spaces survive verbatim.
"""
import json, os, re, signal, subprocess, sys, time, urllib.request, urllib.error

PORT = 8082
BASE = f"http://127.0.0.1:{PORT}"
LOG  = os.path.expanduser("~/buun_vbr/rebench.log")

def log(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def find_server():
    out = subprocess.run(["pgrep", "-f", "buun_vbr/build/bin/llama-server"],
                         capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if p.isdigit()]

def get_argv(pid):
    with open(f"/proc/{pid}/cmdline", "rb") as f:
        parts = f.read().split(b"\0")
    return [p.decode() for p in parts if p]

def wait_health(timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
                if r.status == 200:
                    return time.time() - t0
        except Exception:
            pass
        time.sleep(5)
    return None

def chat(prompt, max_tokens=320, temp=0.0):
    body = json.dumps({"messages":[{"role":"user","content":prompt}],
                       "max_tokens":max_tokens, "temperature":temp,
                       "stream":False}).encode()
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", data=body,
                                 headers={"Content-Type":"application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1200) as r:
        d = json.loads(r.read())
    dt = time.time() - t0
    ch = d["choices"][0]["message"]
    content = ch.get("content") or ""
    reasoning = ch.get("reasoning_content") or ""
    usage = d.get("usage", {})
    return content, reasoning, usage, dt

GARBAGE = re.compile(r"(.)\1{40,}|(/ ){15,}|(\bnull\b\s*){10,}")

def coherent(text):
    """Reject the failure modes we have actually seen: repeated-char spam, '/' loops,
    and empty bodies. Returns (ok, reason)."""
    if not text.strip():
        return False, "EMPTY response body"
    if GARBAGE.search(text):
        return False, "repetition/garbage pattern detected"
    if len(set(text.split())) < 5:
        return False, "vocabulary collapse (<5 unique tokens)"
    return True, "ok"

def main():
    pids = find_server()
    if not pids:
        log("FATAL: no running llama-server found on .73"); return 1
    pid = pids[0]
    argv = get_argv(pid)
    log(f"captured argv from pid {pid} ({len(argv)} args)")
    with open(os.path.expanduser("~/buun_vbr/argv_backup.json"), "w") as f:
        json.dump(argv, f, indent=1)

    log("stopping old server")
    os.kill(pid, signal.SIGTERM)
    for _ in range(60):
        if not find_server(): break
        time.sleep(1)
    else:
        os.kill(pid, signal.SIGKILL); time.sleep(3)

    log("starting new binary with identical argv")
    out = open(os.path.expanduser("~/buun_vbr/server_new.log"), "w")
    subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT,
                     start_new_session=True, stdin=subprocess.DEVNULL)

    el = wait_health()
    if el is None:
        log("FATAL: server did not become healthy in 30 min"); return 2
    log(f"healthy after {el:.0f}s")

    probes = [
        ("coherence-prose", "Explain in three sentences why memory bandwidth, not FLOPs, "
                            "usually limits single-user LLM decode speed.", 320),
        ("coherence-count", "Count from one to forty in words, comma separated. "
                            "Then say DONE.", 400),
        ("speed-long",      "Write a clear 400-word explanation of what a KV cache is "
                            "and why its size matters on consumer GPUs.", 700),
    ]
    results = []
    for name, prompt, mx in probes:
        try:
            content, reasoning, usage, dt = chat(prompt, max_tokens=mx)
        except Exception as e:
            log(f"{name}: REQUEST FAILED {e}"); results.append((name, None)); continue
        ok, why = coherent(content)
        ct = usage.get("completion_tokens", 0)
        tps = ct/dt if dt > 0 else 0
        log(f"{name}: coherent={ok} ({why}) | completion_tokens={ct} | {tps:.2f} t/s | {dt:.1f}s")
        log(f"    reasoning_chars={len(reasoning)} content_chars={len(content)}")
        log(f"    FIRST 240 CHARS >>> {content[:240]!r}")
        log(f"    LAST  120 CHARS >>> {content[-120:]!r}")
        results.append((name, tps if ok else None))

    good = [t for _, t in results if t]
    if good:
        log(f"SUMMARY: best {max(good):.2f} t/s | prior record 22.1-22.3 t/s "
            f"| coherent legs {len(good)}/{len(results)}")
    else:
        log("SUMMARY: NO COHERENT LEG — do not report any throughput number")

    log("server left running for Hermes")
    return 0

if __name__ == "__main__":
    sys.exit(main())
