#!/usr/bin/env python3
"""Driver for PREREG_EXL3_DRAFT_DEPTH.md Amendment 3 (EXL3 campaign, test 6 redone). Runs ON .73.

Depth is a server-level setting on this fork -- per-request `speculative.n_max` is ignored under
draft-mtp -- so this starts one server per (arm, depth) with --draft-max k. Every row is appended,
flushed and fsynced.

Usage (on .73):  python3 exl3_depth_restart.py ALL
"""
import json, os, signal, subprocess, sys, time, urllib.request

QUAL = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin")
OUT = os.path.expanduser("~/exl3_depth2")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8190
H = f"http://127.0.0.1:{PORT}"
EXL3 = "/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw"
EXL3_BYTES = 16860809795
Q6K, Q6K_BYTES = "/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf", 22884408288
MMPROJ = "/mnt/models/AI_Models/Qwen 3.8/mmproj-F16.gguf"
ARMS = [("X", EXL3), ("Q", Q6K)]
DEPTHS = [1, 2, 3, 5]
SPEED = "Write a detailed explanation of how a hash table works."


def flags(k):   # the daily driver's command with --draft-max k
    return ["--mmproj", MMPROJ, "-ngl", "99", "-c", "262144",
            "-ctk", "vbr", "-ctv", "vbr", "--vbr-floor", "t2", "--vbr-vram", "auto",
            "-np", "1", "-fit", "off", "-sm", "tensor", "-fa", "on",
            "--spec-type", "draft-mtp", "--draft-max", str(k), "--jinja", "--kv-unified",
            "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
            "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.0",
            "--presence-penalty", "0.0"]


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "depth2.log"), "a") as f:
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


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def preflight():
    st = sum(os.path.getsize(os.path.join(EXL3, f)) for f in os.listdir(EXL3) if f.endswith(".safetensors"))
    if st != EXL3_BYTES:
        sys.exit(f"PREFLIGHT: EXL3 safetensors total {st} != {EXL3_BYTES}")
    if os.path.getsize(Q6K) != Q6K_BYTES:
        sys.exit(f"PREFLIGHT: {Q6K} is not {Q6K_BYTES} bytes")
    busy = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if busy:
        sys.exit(f"PREFLIGHT: llama-server running (pids {busy})")
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB")
    log(f"preflight ok: GPUs {gpu_mib()} MiB")


def start(label, model, k):
    logf = open(os.path.join(OUT, f"server_{label}_d{k}.log"), "w")
    p = subprocess.Popen([f"{QUAL}/llama-server", "-m", model, *flags(k), "--host", "127.0.0.1",
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


def run(label, model, k):
    base = {"arm": label, "model": model, "depth": k}
    log(f"=== {label} depth {k}")
    p, load_s, err = start(label, model, k)
    if err:
        emit({**base, "stage": "load", "ok": False, "error": err})
        log(f"  LOAD FAILED: {err}")
        stop(p)
        return
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1), "gpu_mib": gpu_mib()})
    try:
        for rep in (1, 2, 3):
            t = req("/completion", {"prompt": SPEED, "n_predict": 256, "temperature": 0, "top_k": 1,
                                    "cache_prompt": False, "ignore_eos": True}).get("timings", {})
            emit({**base, "stage": "depth", "rep": rep, "timings": t})
        log(f"  {t.get('predicted_per_second', 0):.2f} t/s, draft {t.get('draft_n_accepted')}/{t.get('draft_n')}")
    except Exception as e:
        emit({**base, "stage": "error", "error": repr(e)})
        log(f"  STAGE FAILED: {e!r}")
    finally:
        stop(p)


def main():
    os.makedirs(OUT, exist_ok=True)
    preflight()
    v = subprocess.run([f"{QUAL}/llama-server", "--version"], capture_output=True, text=True)
    emit({"stage": "meta", "version": (v.stdout + v.stderr).strip()[-240:], "depths": DEPTHS})
    for label, model in ARMS:
        for k in DEPTHS:
            run(label, model, k)
    log("=== DONE ===")


if __name__ == "__main__":
    main()
