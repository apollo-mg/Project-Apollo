#!/usr/bin/env python3
"""Driver for PREREG_EXL3_GGUF_LADDER_SPEED.md (EXL3 campaign, test 7). Runs ON .73, proxy PAUSED.

Measures served speed for the three options test 3 scored but test 1 never timed: EXL3 5.00bpw,
UD-IQ4_XS and UD-Q4_K_M. Flags and stages are test 1's exactly, so the numbers sit beside its
EXL3 4.00bpw and Q6_K figures. Every row is appended, flushed and fsynced.

Usage (on .73):  python3 exl3_ladder_speed.py ALL
"""
import base64, json, os, re, signal, subprocess, sys, time, urllib.request

QUAL = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin")     # 9ae8f0f40 + e8m0 guard
OUT = os.path.expanduser("~/exl3_ladder")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8190
H = f"http://127.0.0.1:{PORT}"
MMPROJ = "/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf"
TXT = "/mnt/HDD/exl3/wiki.test.raw"
PROBE = os.path.join(OUT, "vision_probe.png")
# All three were hash-verified on .73 during test 3 (the two GGUFs) and its Amendment 2 (the EXL3).
ARMS = [("E5s", "/mnt/HDD/exl3/Qwen3.8-27B-exl3-5.00bpw", 19901680029),   # safetensors only, both copies agree
        ("G4s", "/mnt/HDD/kld/Qwen3.8-27B-UD-IQ4_XS.gguf", 14252845984),
        ("G5s", "/mnt/HDD/kld/Qwen3.8-27B-UD-Q4_K_M.gguf", 16464440224)]
# The daily driver's command, as in test 1.
DAILY = ["--mmproj", MMPROJ, "-ngl", "99", "-c", "262144",
         "-ctk", "vbr", "-ctv", "vbr", "--vbr-floor", "t2", "--vbr-vram", "auto",
         "-np", "1", "-fit", "off", "-sm", "tensor", "-fa", "on",
         "--spec-type", "draft-mtp", "--draft-max", "3", "--jinja", "--kv-unified",
         "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
         "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.0",
         "--presence-penalty", "0.0"]
SPEED = "Write a detailed explanation of how a hash table works."
FACT = "What is the capital of France? Answer with one word."
ASK = "What word is written in this image? Answer with the word only."
OFF = {"enable_thinking": False}


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "ladder.log"), "a") as f:
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


def get(path):
    with urllib.request.urlopen(H + path, timeout=20) as resp:
        return json.loads(resp.read())


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def dir_or_file_bytes(path):
    if os.path.isdir(path):
        return sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path)
                   if f.endswith(".safetensors"))
    return os.path.getsize(path)


def preflight():
    for path in (PROBE, TXT, MMPROJ, f"{QUAL}/llama-server"):
        if not os.path.exists(path):
            sys.exit(f"PREFLIGHT: missing {path}")
    for label, path, size in ARMS:
        got = dir_or_file_bytes(path)
        if got != size:
            sys.exit(f"PREFLIGHT: {label} at {path} is {got} bytes, expected {size}")
    busy = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if busy:
        sys.exit(f"PREFLIGHT: llama-server running (pids {busy}) -- is the wake proxy paused?")
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB")
    log(f"preflight ok: GPUs {gpu_mib()} MiB; all three models match their recorded sizes")


def start(label, model):
    logf = open(os.path.join(OUT, f"server_{label}.log"), "w")
    p = subprocess.Popen([f"{QUAL}/llama-server", "-m", model, *DAILY, "--host", "127.0.0.1",
                          "--port", str(PORT)], stdout=logf, stderr=subprocess.STDOUT,
                         start_new_session=True)
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
        time.sleep(5)
    return p, None, "never answered a real completion within 900 s"


def stop(p):
    if p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    for _ in range(30):
        if all(m < 500 for m in gpu_mib()):
            return
        time.sleep(1)


def chat(content):
    r = req("/v1/chat/completions", {"messages": [{"role": "user", "content": content}],
            "max_tokens": 400, "temperature": 0, "chat_template_kwargs": OFF})
    m = r["choices"][0]["message"]
    return m.get("content"), m.get("reasoning_content")


def complete(body):
    return req("/completion", {**body, "cache_prompt": False, "ignore_eos": True}).get("timings", {})


def run_arm(label, model, _size):
    base = {"arm": label, "model": model}
    log(f"=== {label}: {os.path.basename(model)}")
    p, load_s, err = start(label, model)
    if err:
        emit({**base, "stage": "load", "ok": False, "error": err})
        log(f"  LOAD FAILED: {err}")
        stop(p)
        return
    slot, props = get("/slots")[0], get("/props")
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1), "n_ctx": slot.get("n_ctx"),
          "kv_bpv": slot.get("kv_bpv"), "model_path": props.get("model_path"), "gpu_mib": gpu_mib()})
    log(f"  loaded in {load_s:.0f}s  kv_bpv={slot.get('kv_bpv')} VRAM={gpu_mib()}")
    try:
        c, rc = chat(FACT)
        emit({**base, "stage": "fact", "content": c, "reasoning": rc})
        b64 = base64.b64encode(open(PROBE, "rb").read()).decode()
        c, rc = chat([{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                      {"type": "text", "text": ASK}])
        emit({**base, "stage": "vision", "content": c, "reasoning": rc})
        log(f"  fact/vision: {(c or '').strip()[:40]!r}")
        for rep in (1, 2, 3):
            t = complete({"prompt": SPEED, "n_predict": 256, "temperature": 0, "top_k": 1})
            emit({**base, "stage": "greedy", "rep": rep, "timings": t})
        for rep, seed in ((1, 11), (2, 12), (3, 13)):
            t = complete({"prompt": SPEED, "n_predict": 256, "seed": seed})
            emit({**base, "stage": "sampled", "rep": rep, "seed": seed, "timings": t})
        log(f"  greedy/sampled done")
        text = open(TXT, encoding="utf-8").read()
        for rep, chars in ((1, 4000), (2, 60000)):        # rep 1 is warm-up, rep 2 is scored
            t = complete({"prompt": text[:chars], "n_predict": 1, "temperature": 0})
            emit({**base, "stage": "prefill", "rep": rep, "chars": chars, "timings": t,
                  "kv_bpv_after": get("/slots")[0].get("kv_bpv")})
        log(f"  prefill done")
    except Exception as e:
        emit({**base, "stage": "error", "error": repr(e)})
        log(f"  STAGE FAILED: {e!r}")
    finally:
        stop(p)


def main():
    os.makedirs(OUT, exist_ok=True)
    preflight()
    v = subprocess.run([f"{QUAL}/llama-server", "--version"], capture_output=True, text=True)
    emit({"stage": "meta", "version": (v.stdout + v.stderr).strip()[-240:], "flags": DAILY})
    for arm in ARMS:
        run_arm(*arm)
    log("=== DONE ===")


if __name__ == "__main__":
    main()
