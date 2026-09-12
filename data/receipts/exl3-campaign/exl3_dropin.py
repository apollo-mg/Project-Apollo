#!/usr/bin/env python3
"""Driver for PREREG_EXL3_DROPIN.md (EXL3 campaign, test 1). Runs ON .73, with the wake proxy PAUSED.

Every arm launches llama-server with the daily driver's exact flags, varying only the binary, the
weights and -- for the no-MTP arms -- the two MTP flags. Preflight refuses to start if any
llama-server runs or either GPU holds memory. Every result row is appended, flushed and fsynced as it
is produced. Stages per arm: load, fact, vision (arms with --mmproj), greedy x3, sampled x3, prefill
(warm-up, then the scored ~15k-token prompt).

Usage (on .73):  python3 exl3_dropin.py ALL
"""
import base64, json, os, re, signal, subprocess, sys, time, urllib.request

QUAL = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin")       # 9ae8f0f40 + e8m0 guard
DEPLOYED = os.path.expanduser("~/buun-llama-cpp/build_sm60_head/bin")   # what the wake proxy launches
OUT = os.path.expanduser("~/exl3_dropin")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8190                      # deliberately NOT 8080, the proxy's port
H = f"http://127.0.0.1:{PORT}"
EXL3 = "/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw"
Q6K = "/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf"
MMPROJ = "/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf"
TXT = "/mnt/HDD/exl3/wiki.test.raw"
PROBE = os.path.join(OUT, "vision_probe.png")

# WP_START_CMD as read from systemd on 2026-09-12 at 15:05, minus the shell wrapper, -m, --host, --port.
DAILY = ["--mmproj", MMPROJ, "-ngl", "99", "-c", "262144",
         "-ctk", "vbr", "-ctv", "vbr", "--vbr-floor", "t2", "--vbr-vram", "auto",
         "-np", "1", "-fit", "off", "-sm", "tensor", "-fa", "on",
         "--spec-type", "draft-mtp", "--draft-max", "3", "--jinja", "--kv-unified",
         "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
         "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.0",
         "--presence-penalty", "0.0"]


def drop(flags, *names):
    """Remove each named flag and the one value that follows it."""
    out, skip = [], False
    for f in flags:
        if skip:
            skip = False
        elif f in names:
            skip = True
        else:
            out.append(f)
    return out


def q8_kv(flags):
    """Replace the VBR KV flags with -ctk q8_0 -ctv q8_0."""
    f = drop(flags, "--vbr-floor", "--vbr-vram")
    return [("q8_0" if i and f[i - 1] in ("-ctk", "-ctv") else x) for i, x in enumerate(f)]


NO_MTP = drop(DAILY, "--spec-type", "--draft-max")
ARMS = [("X", QUAL, EXL3, DAILY), ("Xn", QUAL, EXL3, NO_MTP),
        ("Q", QUAL, Q6K, DAILY), ("Qn", QUAL, Q6K, NO_MTP),
        ("D", DEPLOYED, Q6K, DAILY)]
LADDER = [("X-nomm", QUAL, EXL3, drop(DAILY, "--mmproj")),          # only if X fails to load
          ("X-novbr", QUAL, EXL3, q8_kv(DAILY)),
          ("X-bare", QUAL, EXL3, q8_kv(drop(NO_MTP, "--mmproj")))]
SPEED = "Write a detailed explanation of how a hash table works."    # as in the inference receipt
FACT = "What is the capital of France? Answer with one word."
ASK = "What word is written in this image? Answer with the word only."
OFF = {"enable_thinking": False}


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "dropin.log"), "a") as f:
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


def server_log(label, pattern=None, last=None):
    with open(os.path.join(OUT, f"server_{label}.log"), errors="replace") as f:
        lines = [l.rstrip()[:240] for l in f]
    if pattern:
        rx = re.compile(pattern, re.I)
        lines = [l for l in lines if rx.search(l)][:20]
    return lines[-last:] if last else lines


def preflight():
    for path in (PROBE, TXT, EXL3, Q6K, MMPROJ, f"{QUAL}/llama-server", f"{DEPLOYED}/llama-server"):
        if not os.path.exists(path):
            sys.exit(f"PREFLIGHT: missing {path}")
    busy = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if busy:
        sys.exit(f"PREFLIGHT: llama-server already running (pids {busy}) -- is the wake proxy paused?")
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB -- refusing to share them")
    log(f"preflight ok: GPUs {gpu_mib()} MiB, no llama-server")


def start(label, bindir, model, flags):
    logf = open(os.path.join(OUT, f"server_{label}.log"), "w")
    p = subprocess.Popen([f"{bindir}/llama-server", "-m", model, *flags, "--host", "127.0.0.1",
                          "--port", str(PORT)], stdout=logf, stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 900:
        if p.poll() is not None:
            return p, None, f"server exited rc={p.returncode} (see server_{label}.log)"
        try:
            r = req("/v1/chat/completions",
                    {"messages": [{"role": "user", "content": "Say READY"}], "max_tokens": 4}, timeout=30)
            if "choices" in r:      # readiness is a real completion, never /health
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


def run_arm(label, bindir, model, flags):
    base = {"arm": label, "bin": bindir, "model": model, "flags": flags}
    log(f"=== {label}: {os.path.basename(model)} via {bindir}")
    p, load_s, err = start(label, bindir, model, flags)
    if err:
        log(f"  LOAD FAILED: {err}")
        emit({**base, "stage": "load", "ok": False, "error": err, "tail": server_log(label, last=15)})
        stop(p)
        return False
    slot, props = get("/slots")[0], get("/props")
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1), "n_ctx": slot.get("n_ctx"),
          "kv_bpv": slot.get("kv_bpv"), "model_path": props.get("model_path"), "gpu_mib": gpu_mib(),
          "mtp_log": server_log(label, r"nextn|mtp|draft|specul")})
    log(f"  loaded in {load_s:.0f}s  n_ctx={slot.get('n_ctx')} kv_bpv={slot.get('kv_bpv')} VRAM={gpu_mib()}")
    try:
        c, rc = chat(FACT)
        emit({**base, "stage": "fact", "content": c, "reasoning": rc})
        log(f"  fact: {(c or '').strip()[:60]!r}")
        if "--mmproj" in flags:
            b64 = base64.b64encode(open(PROBE, "rb").read()).decode()
            c, rc = chat([{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                          {"type": "text", "text": ASK}])
            emit({**base, "stage": "vision", "content": c, "reasoning": rc})
            log(f"  vision: {(c or '').strip()[:60]!r}")
        for rep in (1, 2, 3):
            t = complete({"prompt": SPEED, "n_predict": 256, "temperature": 0, "top_k": 1})
            emit({**base, "stage": "greedy", "rep": rep, "timings": t})
            log(f"  greedy {rep}: {t.get('predicted_per_second', 0):.2f} t/s  draft {t.get('draft_n_accepted')}/{t.get('draft_n')}")
        for rep, seed in ((1, 11), (2, 12), (3, 13)):
            t = complete({"prompt": SPEED, "n_predict": 256, "seed": seed})   # the server's own sampling
            emit({**base, "stage": "sampled", "rep": rep, "seed": seed, "timings": t})
            log(f"  sampled {rep}: {t.get('predicted_per_second', 0):.2f} t/s  draft {t.get('draft_n_accepted')}/{t.get('draft_n')}")
        text = open(TXT, encoding="utf-8").read()
        for rep, chars in ((1, 4000), (2, 60000)):                         # rep 1 is warm-up
            t = complete({"prompt": text[:chars], "n_predict": 1, "temperature": 0})
            emit({**base, "stage": "prefill", "rep": rep, "chars": chars, "timings": t,
                  "kv_bpv_after": get("/slots")[0].get("kv_bpv")})
            log(f"  prefill {rep}: {t.get('prompt_n')} tok at {t.get('prompt_per_second', 0):.1f} t/s")
    except Exception as e:
        log(f"  STAGE FAILED: {e!r}")
        emit({**base, "stage": "error", "error": repr(e), "tail": server_log(label, last=15)})
    finally:
        stop(p)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    preflight()
    for name, b in (("QUAL", QUAL), ("DEPLOYED", DEPLOYED)):
        v = subprocess.run([f"{b}/llama-server", "--version"], capture_output=True, text=True)
        emit({"stage": "meta", "bin": name, "path": b, "version": (v.stdout + v.stderr).strip()[-240:]})
    if not run_arm(*ARMS[0]):
        for arm in LADDER:
            run_arm(*arm)
    for arm in ARMS[1:]:
        run_arm(*arm)
    log("=== DONE ===")


if __name__ == "__main__":
    main()
