#!/usr/bin/env python3
"""Driver for PREREG_EXL3_SM60_INFERENCE.md. Runs ON .73, with the wake proxy PAUSED.

The proxy runs `pkill -x llama-server` before every idle suspend, so a test server can only survive
the run if the proxy is stopped first (`systemctl --user stop apollo-wake-proxy` on the control
plane). Preflight refuses to start if any llama-server is running or either GPU holds memory.

Every result row is appended, flushed and fsynced as it is produced. Stages:
  load    server comes up; records n_ctx, kv_bpv (must be f16), model_path, VRAM, load time
  fact    one factual question, thinking off, temperature 0              -> P-X1 / P-X2
  greedy  raw completion, 64 tokens, top_k 1, no prompt cache            -> P-X4 (path agreement)
  speed   3 x 256 decoded tokens, ignore_eos, server timings             -> P-X5 / P-X6
  ppl     llama-perplexity, wikitext-2 test, -c 512 --chunks 40          -> P-X3

Usage (on .73):  python3 exl3_sm60_qual.py ALL      or one of: X-06 X-27 X-27-cublas Q6K PPL
Amendment 1 adds X-27-tensor and Q6K-tensor (-sm tensor -fit off); they are not part of ALL.
"""
import json, os, re, signal, subprocess, sys, time, urllib.request

BIN = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin")
OUT = os.path.expanduser("~/exl3_qual")
RES = os.path.join(OUT, "results.jsonl")
PORT = 8190                      # deliberately NOT 8080, the proxy's port
H = f"http://127.0.0.1:{PORT}"
MODELS = {
    "X-06": "/mnt/HDD/exl3/Qwen3-0.6B-exl3-4.0bpw",
    "X-27": "/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw",
    "Q6K":  "/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf",
}
TXT = "/mnt/HDD/exl3/wiki.test.raw"
# Matched for every model (prereg). f16 KV passed explicitly: buun's fork defaults to VBR.
FLAGS = ["-ngl", "99", "-sm", "layer", "-c", "8192", "-np", "1", "-fa", "on",
         "-ctk", "f16", "-ctv", "f16", "--jinja"]
# Amendment 1 (tensor split, requested by buun). `-fit off` is copied from the daily driver's
# known-good `-sm tensor` launch on this box; expected inert at explicit -c/-ngl, declared anyway.
FLAGS_TENSOR = [("tensor" if f == "layer" else f) for f in FLAGS] + ["-fit", "off"]
FACT = "What is the capital of France? Answer with one word."
GREEDY = "The history of the Roman Empire"
SPEED = "Write a detailed explanation of how a hash table works."


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "qual.log"), "a") as f:
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


def preflight():
    busy = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if busy:
        sys.exit(f"PREFLIGHT: llama-server already running (pids {busy}) -- is the wake proxy paused?")
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB -- refusing to share them")
    log(f"preflight ok: GPUs {gpu_mib()} MiB, no llama-server")


def start(model, env_extra, label, flags=FLAGS):
    env = dict(os.environ, **env_extra)
    logf = open(os.path.join(OUT, f"server_{label}.log"), "w")
    p = subprocess.Popen([f"{BIN}/llama-server", "-m", model, *flags, "--host", "127.0.0.1",
                          "--port", str(PORT)], stdout=logf, stderr=subprocess.STDOUT,
                         env=env, start_new_session=True)
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


def run_model(label, model, env_extra, flags=FLAGS):
    base = {"label": label, "model": model, "env": env_extra, "flags": flags}
    log(f"=== {label}: {model} {env_extra or ''}")
    p, load_s, err = start(model, env_extra, label, flags)
    if err:
        log(f"  LOAD FAILED: {err}")
        emit({**base, "stage": "load", "ok": False, "error": err})
        stop(p)
        return
    slots, props = get("/slots")[0], get("/props")
    emit({**base, "stage": "load", "ok": True, "load_s": round(load_s, 1),
          "n_ctx": slots.get("n_ctx"), "kv_bpv": slots.get("kv_bpv"),
          "model_path": props.get("model_path"), "gpu_mib": gpu_mib()})
    log(f"  loaded in {load_s:.0f}s  n_ctx={slots.get('n_ctx')} kv_bpv={slots.get('kv_bpv')} VRAM={gpu_mib()}")
    try:
        r = req("/v1/chat/completions", {"messages": [{"role": "user", "content": FACT}],
                "max_tokens": 64, "temperature": 0,
                "chat_template_kwargs": {"enable_thinking": False}})
        msg = r["choices"][0]["message"]
        emit({**base, "stage": "fact", "content": msg.get("content"),
              "reasoning": msg.get("reasoning_content")})
        log(f"  fact: {(msg.get('content') or '').strip()[:80]!r}")

        r = req("/completion", {"prompt": GREEDY, "n_predict": 64, "temperature": 0, "top_k": 1,
                                "cache_prompt": False})
        emit({**base, "stage": "greedy", "content": r.get("content"),
              "tokens_predicted": r.get("tokens_predicted")})
        log(f"  greedy: {(r.get('content') or '')[:80]!r}")

        for rep in (1, 2, 3):
            r = req("/completion", {"prompt": SPEED, "n_predict": 256, "temperature": 0, "top_k": 1,
                                    "cache_prompt": False, "ignore_eos": True})
            t = r.get("timings", {})
            emit({**base, "stage": "speed", "rep": rep, "predicted_n": t.get("predicted_n"),
                  "predicted_per_second": t.get("predicted_per_second"),
                  "prompt_per_second": t.get("prompt_per_second")})
            log(f"  speed rep {rep}: {t.get('predicted_per_second', 0):.2f} t/s decode")
    except Exception as e:
        log(f"  STAGE FAILED: {e!r}")
        emit({**base, "stage": "error", "error": repr(e)})
    finally:
        stop(p)


def ppl(label, model):
    cmd = [f"{BIN}/llama-perplexity", "-m", model, "-f", TXT, "-c", "512", "--chunks", "40",
           "-ngl", "99", "-sm", "layer", "-fa", "on", "-ctk", "f16", "-ctv", "f16"]
    log(f"=== PPL {label}")
    t0 = time.time()
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
    text = out.stdout + out.stderr
    with open(os.path.join(OUT, f"ppl_{label}.log"), "w") as f:
        f.write(text)
    m = re.search(r"Final estimate: PPL = ([\d.]+) \+/- ([\d.]+)", text)
    emit({"label": label, "stage": "ppl", "model": model, "rc": out.returncode,
          "ppl": float(m.group(1)) if m else None, "ppl_err": float(m.group(2)) if m else None,
          "wall_s": round(time.time() - t0, 1)})
    log(f"  PPL {label}: {m.group(1) + ' +/- ' + m.group(2) if m else 'NOT PRODUCED, rc=' + str(out.returncode)}")


def main():
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    preflight()
    if what in ("ALL", "X-06"):
        run_model("X-06", MODELS["X-06"], {})
    if what in ("ALL", "X-27"):
        run_model("X-27", MODELS["X-27"], {})
    if what in ("ALL", "X-27-cublas"):
        run_model("X-27-cublas", MODELS["X-27"], {"GGML_EXL3_INT8": "0"})
    if what in ("ALL", "Q6K"):
        run_model("Q6K", MODELS["Q6K"], {})
    if what == "X-27-tensor":
        run_model("X-27-tensor", MODELS["X-27"], {}, FLAGS_TENSOR)
    if what == "Q6K-tensor":
        run_model("Q6K-tensor", MODELS["Q6K"], {}, FLAGS_TENSOR)
    if what in ("ALL", "PPL"):
        for label in ("X-27", "Q6K", "X-06"):
            ppl(label, MODELS[label])
    log("=== DONE ===")


if __name__ == "__main__":
    main()
