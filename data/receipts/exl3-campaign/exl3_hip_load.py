#!/usr/bin/env python3
"""Driver and scorer for PREREG_EXL3_HIP_LOAD.md (EXL3 campaign, test 2). Runs on the control plane.

Every result row is appended, flushed and fsynced as it is produced.
Usage:  exl3_hip_load.py primary | secondary | score
"""
import json, os, re, signal, statistics, subprocess, sys, time, urllib.request

BIN = "/mnt/TG_2TB/Projects/buun-9ae8f/build_rocm/bin"          # buun 9ae8f0f40, gfx1201
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hip")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8195
H = f"http://127.0.0.1:{PORT}"
MODELS = {"primary": ("H-06", "/mnt/TG_2TB/AI/Models/exl3/Qwen3-0.6B-exl3-4.0bpw"),
          "secondary": ("H-27", "/mnt/TG_2TB/AI/Models/exl3/Qwen3.8-27B-exl3-4.00bpw")}
# f16 KV passed explicitly: buun's fork defaults to VBR.
FLAGS = ["-ngl", "99", "-c", "4096", "-np", "1", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "--jinja"]
FACT = "What is the capital of France? Answer with one word."
SPEED = "Write a detailed explanation of how a hash table works."
BUF = re.compile(r"(\S+) model buffer size\s*=\s*([\d.]+) MiB")
# The 18 GB start guard is the 27B's (~14 GB of weights in system RAM), as the prereg states; the 0.6B
# needs only headroom. First version applied 18 GB to both and refused the 0.6B at 17.8 GB (no data).
MIN_START_GB = {"primary": 4, "secondary": 18}
MIN_RUN_GB = 3


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "hip.log"), "a") as f:
        f.write(line + "\n")


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def req(path, body, timeout=900):
    r = urllib.request.Request(H + path, data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def mem_available_gb():
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576
    return 0.0


def buffers(logpath):
    out = {}
    with open(logpath, errors="replace") as f:
        for m in BUF.finditer(f.read()):
            out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(2))
    return out


def stop(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()


def run(which):
    label, model = MODELS[which]
    base = {"arm": label, "model": model, "flags": FLAGS}
    try:
        urllib.request.urlopen(H + "/health", timeout=3)
        sys.exit(f"PREFLIGHT: something already answers on port {PORT}")
    except OSError:
        pass
    if mem_available_gb() < MIN_START_GB[which]:
        sys.exit(f"PREFLIGHT: MemAvailable {mem_available_gb():.1f} GB < {MIN_START_GB[which]} GB")
    v = subprocess.run([f"{BIN}/llama-server", "--version"], capture_output=True, text=True)
    emit({**base, "stage": "meta", "version": (v.stdout + v.stderr).strip()[-200:]})
    logpath = os.path.join(OUT, f"server_{label}.log")
    log(f"=== {label}: {model}")
    p = subprocess.Popen([f"{BIN}/llama-server", "-m", model, *FLAGS, "--host", "127.0.0.1",
                          "--port", str(PORT)], stdout=open(logpath, "w"), stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0, err, low = time.time(), None, 99.0
    try:
        while True:
            low = min(low, mem_available_gb())
            if low < MIN_RUN_GB:
                err = f"memory abort: MemAvailable fell to {low:.1f} GB"
                break
            if p.poll() is not None:
                err = f"server exited rc={p.returncode}"
                break
            if time.time() - t0 > 900:
                err = "never answered a real completion within 900 s"
                break
            try:
                if "choices" in req("/v1/chat/completions", {"messages": [{"role": "user", "content": "Say READY"}],
                                                             "max_tokens": 4}, timeout=30):
                    break                      # readiness is a real completion, never /health
            except Exception:
                pass
            time.sleep(3)
        if err:
            with open(logpath, errors="replace") as f:
                tail = [l.rstrip()[:240] for l in f][-15:]
            emit({**base, "stage": "load", "ok": False, "error": err, "buffers": buffers(logpath),
                  "min_mem_available_gb": round(low, 1), "tail": tail})
            log(f"  LOAD FAILED: {err}")
            return
        emit({**base, "stage": "load", "ok": True, "load_s": round(time.time() - t0, 1),
              "buffers": buffers(logpath), "min_mem_available_gb": round(low, 1)})
        log(f"  loaded in {time.time() - t0:.0f}s  buffers={buffers(logpath)}")
        r = req("/v1/chat/completions", {"messages": [{"role": "user", "content": FACT}], "max_tokens": 64,
                "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}})
        msg = r["choices"][0]["message"]
        emit({**base, "stage": "fact", "content": msg.get("content"), "reasoning": msg.get("reasoning_content")})
        log(f"  fact: {(msg.get('content') or '').strip()[:60]!r}")
        for rep in (1, 2, 3):
            t = req("/completion", {"prompt": SPEED, "n_predict": 128, "temperature": 0, "top_k": 1,
                                    "cache_prompt": False, "ignore_eos": True}).get("timings", {})
            emit({**base, "stage": "speed", "rep": rep, "timings": t, "mem_available_gb": round(mem_available_gb(), 1)})
            log(f"  speed {rep}: {t.get('predicted_per_second', 0):.2f} t/s")
    except Exception as e:
        emit({**base, "stage": "error", "error": repr(e)})
        log(f"  STAGE FAILED: {e!r}")
    finally:
        stop(p)


def score():
    if not os.path.exists(RES):
        sys.exit(f"no results yet: {RES}")
    rows = [json.loads(l) for l in open(RES) if l.strip()]
    of = lambda arm, st: [r for r in rows if r.get("arm") == arm and r.get("stage") == st]
    ok = lambda arm: bool(of(arm, "load")) and bool(of(arm, "load")[-1].get("ok"))
    verdict = lambda b: "CONFIRMED" if b else "FALSIFIED"
    for arm in ("H-06", "H-27"):
        for r in of(arm, "load") + of(arm, "error"):
            print(f"{arm} {r['stage']}: ok={r.get('ok')} {r.get('error') or ''} load_s={r.get('load_s')} "
                  f"buffers={r.get('buffers')} min_mem={r.get('min_mem_available_gb')}")
            for line in r.get("tail") or []:
                print("   ", line)
    P = {"P-H1": verdict(ok("H-06")) if of("H-06", "load") else "NOT RUN"}
    if ok("H-06"):
        b = of("H-06", "load")[-1].get("buffers") or {}
        cpu = sum(v for k, v in b.items() if "CPU" in k.upper())
        gpu = sum(v for k, v in b.items() if "ROCM" in k.upper())
        P["P-H2"] = f"{verdict(cpu > gpu)} (CPU {cpu:.1f} MiB vs ROCm {gpu:.1f} MiB)" if b else "NOT SCORABLE (no buffer lines)"
        f = of("H-06", "fact")
        P["P-H3"] = f"{verdict(bool(f) and 'paris' in (f[-1].get('content') or '').lower())} ({(f[-1].get('content') if f else None)!r})"
    if of("H-27", "load"):
        P["P-H4"] = verdict(ok("H-27"))
        v = [r["timings"].get("predicted_per_second") for r in of("H-27", "speed") if r.get("timings")]
        P["P-H5"] = (f"{verdict(statistics.median(v) < 3.0)} (median {statistics.median(v):.2f} t/s over {len(v)})"
                     if len(v) == 3 else "NOT TESTABLE (fewer than 3 speed reps)")
    else:
        P["P-H4"] = P["P-H5"] = "NOT RUN"
    for k in ("P-H1", "P-H2", "P-H3", "P-H4", "P-H5"):
        print(f"- **{k}**: {P.get(k, 'NOT TESTABLE (H-06 did not load)')}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what in MODELS:
        run(what)
    elif what == "score":
        score()
    else:
        sys.exit(__doc__)
