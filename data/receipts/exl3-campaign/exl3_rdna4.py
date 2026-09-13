#!/usr/bin/env python3
"""Driver and scorer for PREREG_EXL3_RDNA4.md (EXL3 campaign, test 8). Runs on the control plane.

Verifies buun's HIP EXL3 port (da458765d) on the only RDNA4 card in the collaboration. Every row is
appended, flushed and fsynced.

Usage:  exl3_rdna4.py tests | models | ab | score
"""
import json, os, re, signal, statistics, subprocess, sys, time, urllib.request

BUILD = "/mnt/TG_2TB/Projects/buun-da458/build_rocm"
BIN = f"{BUILD}/bin"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rdna4")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8195
H = f"http://127.0.0.1:{PORT}"
MODELS = {"H-06": "/mnt/TG_2TB/AI/Models/exl3/Qwen3-0.6B-exl3-4.0bpw",
          "H-27-3": "/mnt/TG_2TB/AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw"}
FLAGS = ["-c", "4096", "-np", "1", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "--jinja"]
FACT = "What is the capital of France? Answer with one word."
SPEED = "Write a detailed explanation of how a hash table works."
# test 2 (RESULT_EXL3_HIP.md), same card, model and flags, at 9ae8f0f40 with EXL3 compiled out of HIP
BASE = {"primary_median": 6.47, "ngl99": 4.48, "ngl0": 5.24, "vram99": 0.82, "vram0": 0.25}


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "rdna4.log"), "a") as f:
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


def vram_gb():
    out = subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--csv"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) > 2 and parts[0].startswith("card"):
            try:
                return int(parts[2]) / 1e9
            except ValueError:
                pass
    return 0.0


def start(label, model, ngl):
    logf = open(os.path.join(OUT, f"server_{label}_ngl{ngl}.log"), "w")
    p = subprocess.Popen([f"{BIN}/llama-server", "-m", model, "-ngl", str(ngl), *FLAGS,
                          "--host", "127.0.0.1", "--port", str(PORT)],
                         stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 900:
        if p.poll() is not None:
            return p, None, f"server exited rc={p.returncode}"
        try:
            if "choices" in req("/v1/chat/completions",
                                {"messages": [{"role": "user", "content": "Say READY"}], "max_tokens": 4},
                                timeout=60):
                return p, time.time() - t0, None
        except Exception:
            pass
        time.sleep(3)
    return p, None, "never answered a real completion within 900 s"


def stop(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    time.sleep(3)


def speed(n, reps=3):
    out = []
    for _ in range(reps):
        t = req("/completion", {"prompt": SPEED, "n_predict": n, "temperature": 0, "top_k": 1,
                                "cache_prompt": False, "ignore_eos": True}).get("timings", {})
        out.append(t)
    return out


def run_model(label, model, ngl=99, reps=3, n=128):
    base = {"arm": label, "model": model, "ngl": ngl}
    before = vram_gb()
    log(f"=== {label} at -ngl {ngl} (VRAM before {before:.2f} GB)")
    p, load_s, err = start(label, model, ngl)
    if err:
        emit({**base, "stage": "load", "ok": False, "error": err})
        log(f"  LOAD FAILED: {err}")
        stop(p)
        return
    rss = int(subprocess.run(["ps", "-o", "rss=", "-p", str(p.pid)],
                             capture_output=True, text=True).stdout.strip() or 0) / 1048576
    after = vram_gb()
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1),
          "vram_before_gb": round(before, 2), "vram_after_gb": round(after, 2),
          "vram_delta_gb": round(after - before, 2), "rss_gb": round(rss, 2)})
    log(f"  loaded in {load_s:.0f}s  VRAM +{after - before:.2f} GB  RSS {rss:.2f} GB")
    try:
        r = req("/v1/chat/completions", {"messages": [{"role": "user", "content": FACT}],
                "max_tokens": 64, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}})
        msg = r["choices"][0]["message"]
        emit({**base, "stage": "fact", "content": msg.get("content")})
        log(f"  fact: {(msg.get('content') or '').strip()[:40]!r}")
        for i, t in enumerate(speed(n, reps), 1):
            emit({**base, "stage": "speed", "rep": i, "timings": t})
            log(f"  speed {i}: {t.get('predicted_per_second', 0):.2f} t/s")
    except Exception as e:
        emit({**base, "stage": "error", "error": repr(e)})
        log(f"  STAGE FAILED: {e!r}")
    finally:
        stop(p)


def run_tests():
    log("=== buun's EXL3 test suite on gfx1201")
    p = subprocess.run(["ctest", "--test-dir", BUILD, "-R", "exl3", "--output-on-failure"],
                       capture_output=True, text=True, timeout=3600)
    text = p.stdout + p.stderr
    with open(os.path.join(OUT, "ctest.log"), "w") as f:
        f.write(text)
    # ctest prints "<status>   <seconds>"; keep only the first word, or every test reads as a failure.
    results = re.findall(r"Test\s+#\d+:\s+(\S+)\s+\.+\s*(\*{3}\s*)?(\w[\w ]*)", text)
    emit({"stage": "ctest", "rc": p.returncode,
          "tests": [{"name": n, "status": s.split()[0] if s.split() else s} for n, _, s in results],
          "summary": text.strip().splitlines()[-1] if text.strip() else ""})
    for n, _, s in results:
        log(f"  {n}: {s.strip()}")
    log(f"  ctest rc={p.returncode}")


def score():
    if not os.path.exists(RES):
        sys.exit(f"no results yet: {RES}")
    rows = [json.loads(l) for l in open(RES) if l.strip()]

    def of(arm, ngl, stage):
        return [r for r in rows if r.get("arm") == arm and r.get("ngl") == ngl and r.get("stage") == stage]

    def dec(arm, ngl):
        v = [x for x in ((r.get("timings") or {}).get("predicted_per_second") for r in of(arm, ngl, "speed")) if x]
        return statistics.median(v) if v else None

    def load(arm, ngl):
        ld = of(arm, ngl, "load")
        return ld[-1] if ld else {}

    def verdict(b):
        return "CONFIRMED" if b else "FALSIFIED"

    ct = [r for r in rows if r.get("stage") == "ctest"]
    print("| arm | ngl | loaded | load s | VRAM delta GB | RSS GB | decode t/s | fact |")
    print("|---|---|---|---|---|---|---|---|")
    for arm in ("H-06", "H-27-3"):
        for ngl in (99, 0):
            ld = load(arm, ngl)
            if not ld:
                continue
            f = of(arm, ngl, "fact")
            print(f"| {arm} | {ngl} | {ld.get('ok')} | {ld.get('load_s')} | {ld.get('vram_delta_gb')} | "
                  f"{ld.get('rss_gb')} | {dec(arm, ngl) or '-'} | "
                  f"{(f[-1].get('content') or '').strip()[:20]!r} |")
    print(f"\n(test 2 baseline at 9ae8f0f40: H-06 median {BASE['primary_median']} t/s; "
          f"-ngl 99 {BASE['ngl99']} vs -ngl 0 {BASE['ngl0']} t/s; VRAM +{BASE['vram99']} / +{BASE['vram0']} GB)")

    print("\n## Predictions\n")
    hip = f"{BIN}/../ggml/src/ggml-hip/libggml-hip.so"
    lib = hip if os.path.exists(hip) else f"{BIN}/libggml-hip.so"
    cuda_only = exl3 = None
    if os.path.exists(lib):
        blob = open(lib, "rb").read()
        cuda_only = blob.count(b"EXL3 is CUDA only")
        exl3 = blob.lower().count(b"exl3")
    print(f"- **P-R1**: " + ("NOT TESTABLE (no libggml-hip.so found)" if cuda_only is None else
                             f"{verdict(cuda_only == 0 and exl3 > 0)} ('EXL3 is CUDA only' x{cuda_only}, 'exl3' x{exl3})"))
    if ct:
        tests = [{"name": t["name"], "status": str(t["status"]).split()[0]} for t in ct[-1]["tests"]]
        bad = [t for t in tests if t["status"] not in ("Passed", "Skipped")]
        print(f"- **P-R2**: {verdict(bool(tests) and not bad)} ({len(tests)} tests; " +
              ", ".join(f"{t['name']} {t['status']}" for t in tests[:6]) + (f"; failures: {bad}" if bad else "") + ")")
    else:
        print("- **P-R2**: NOT RUN")
    facts = {a: (of(a, 99, "fact")[-1].get("content") or "").lower() if of(a, 99, "fact") else "" for a in MODELS}
    print(f"- **P-R3**: {verdict(all('paris' in v for v in facts.values()))} ({ {k: v.strip()[:12] for k, v in facts.items()} })")
    d99, d0 = dec("H-06", 99), dec("H-06", 0)
    print(f"- **P-R4**: " + ("NOT TESTABLE" if None in (d99, d0) else
                             f"{verdict(d99 > d0)} (-ngl 99 {d99:.2f} vs -ngl 0 {d0:.2f}; test 2 had {BASE['ngl99']} vs {BASE['ngl0']})"))
    print(f"- **P-R5**: " + ("NOT TESTABLE" if d99 is None else
                             f"{verdict(d99 >= 3 * BASE['primary_median'])} ({d99:.2f} vs 3x{BASE['primary_median']} = {3 * BASE['primary_median']:.2f})"))
    v = load("H-06", 99).get("vram_delta_gb")
    print(f"- **P-R6**: " + ("NOT TESTABLE" if v is None else
                             f"{verdict(v >= 1.4)} (VRAM delta {v} GB vs test 2's {BASE['vram99']})"))
    d27 = dec("H-27-3", 99)
    print(f"- **P-R7**: " + ("NOT TESTABLE" if d27 is None else f"{verdict(d27 > 6.0)} ({d27:.2f} t/s)"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "tests":
        run_tests()
    elif what == "models":
        for label, model in MODELS.items():
            run_model(label, model, ngl=99)
    elif what == "ab":
        run_model("H-06", MODELS["H-06"], ngl=0, reps=3, n=128)
    elif what == "score":
        score()
    else:
        sys.exit(__doc__)
