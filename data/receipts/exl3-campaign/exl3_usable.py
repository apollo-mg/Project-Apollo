#!/usr/bin/env python3
"""Test 11 driver — PREREG_EXL3_USABLE.md with Amendments 1-4. Runs ON .194, launched detached.

Two arms in parallel, each with its own socket and its own two cards (Stage 1 measured cross-socket reads at
7.0 GB/s against 22.7 local, so the arms are kept out of each other's memory):

    exl3  EXL3 3.00bpw            GPUs 0,1   NUMA node 0   port 8101
    gguf  UD-IQ3_XXS @ f9758630   GPUs 2,3   NUMA node 1   port 8102

Both servers run -np 1 at temperature 0 with thinking off and one pinned chat template, so neither arm's load can
change the other's output. Wall-clock is recorded but not scored. Checks ABORT; they never warn and continue.

Usage (on .194):  python3 exl3_usable.py
"""
import json, os, re, subprocess, sys, threading, time, urllib.request

H = os.path.expanduser("~")
W = os.path.join(H, "test11")
RES = os.path.join(W, "results.jsonl")
BIN = os.path.join(H, "buun-c7f114d34/build_sm60/bin/llama-server")
COMMIT = "c7f114d34"
EXL3 = os.path.join(H, "AI/Models/exl3/Qwen3.8-27B-exl3-3.00bpw")
GGUF = os.path.join(H, "AI/Models/qwen27b/Qwen3.8-27B-UD-IQ3_XXS.gguf")
GGUF_SHA = "0a6129dcbbbe72f423dc67e0e3bbfbbdf3e923981a3637687ebb96a46c59d6be"   # unsloth rev f9758630
MANIFEST = os.path.join(H, "test11_manifest_exl3.txt")
TEMPLATE = os.path.join(EXL3, "chat_template.jinja")
DATASET = os.path.join(W, "humanevalplus.jsonl")
DATASET_BYTES, DATASET_N = 11_317_638, 164        # fetch_dataset.py's recorded fingerprint
HEP = os.path.join(W, "hep_eval.py")
COMMON = ["-c", "8192", "-np", "1", "-fa", "on", "-ctk", "f16", "-ctv", "f16", "-sm", "layer",
          "-ngl", "99", "-fit", "off", "--jinja", "--chat-template-file", TEMPLATE, "--host", "127.0.0.1"]
ARMS = [
    ("exl3", EXL3, 8101, "0,1", "0"),
    ("gguf", GGUF, 8102, "2,3", "1"),
]


class Abort(Exception):
    pass


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(W, "driver.log"), "a") as f:
        f.write(line + "\n")


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def sha256(path):
    return subprocess.run(["sha256sum", path], capture_output=True, text=True, check=True).stdout.split()[0]


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def gates():
    for p in (BIN, EXL3, GGUF, MANIFEST, TEMPLATE, DATASET, HEP):
        if not os.path.exists(p):
            raise Abort(f"missing {p}")
    v = subprocess.run([BIN, "--version"], capture_output=True, text=True)
    ver = (v.stdout + v.stderr).strip()
    if COMMIT not in ver:
        raise Abort(f"llama-server --version does not report {COMMIT}: {ver[:200]}")
    c = subprocess.run(["sha256sum", "-c", MANIFEST, "--quiet"], cwd=EXL3, capture_output=True, text=True)
    if c.returncode != 0:
        raise Abort(f"EXL3 snapshot fails its manifest: {c.stdout[-300:]}{c.stderr[-300:]}")
    got = sha256(GGUF)
    if got != GGUF_SHA:
        raise Abort(f"GGUF sha256 {got} != {GGUF_SHA} (unsloth rev f9758630)")
    n_bytes = os.path.getsize(DATASET)
    with open(DATASET) as f:
        n_lines = sum(1 for l in f if l.strip())
    if n_bytes != DATASET_BYTES or n_lines != DATASET_N:
        raise Abort(f"dataset is {n_bytes} B / {n_lines} problems, expected {DATASET_BYTES} / {DATASET_N}")
    if any(m > 500 for m in gpu_mib()):
        raise Abort(f"GPUs not empty: {gpu_mib()} MiB")
    if subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True).returncode == 0:
        raise Abort("a llama-server is already running")
    if subprocess.run(["which", "numactl"], capture_output=True).returncode != 0:
        raise Abort("numactl is not installed")
    return ver, sha256(TEMPLATE), sha256(HEP)


def start(arm, model, port, gpus, node):
    env = {**os.environ, "GGML_CUDA_ALLREDUCE": "internal", "CUDA_VISIBLE_DEVICES": gpus}
    cmd = ["numactl", f"--cpunodebind={node}", f"--membind={node}", BIN, "-m", model, *COMMON,
           "--port", str(port)]
    lf = open(os.path.join(W, f"server_{arm}.log"), "w")
    p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env)
    return p, lf, cmd


def healthy(p, port, limit=1800):
    t0 = time.time()
    while time.time() - t0 < limit:
        if p.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def chat(port, content, max_tokens=256, timeout=900):
    body = json.dumps({"messages": [{"role": "user", "content": content}], "max_tokens": max_tokens,
                       "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        m = json.loads(r.read())["choices"][0]["message"]
    return (m.get("content") or "") + (m.get("reasoning_content") or "")


def kv_types(path):
    with open(path, errors="replace") as f:
        return sorted(set(re.findall(r"\b[KV] \((\w+)\)", f.read())))


def main():
    os.makedirs(W, exist_ok=True)
    servers = []
    try:
        ver, tpl_sha, hep_sha = gates()
        emit({"stage": "gates", "ok": True, "version": ver[:200], "template_sha256": tpl_sha,
              "hep_eval_sha256": hep_sha, "gguf_sha256": GGUF_SHA, "gguf_revision": "f9758630"})
        log(f"gates passed -- template {tpl_sha[:16]}, hep_eval {hep_sha[:16]}")

        for arm, model, port, gpus, node in ARMS:
            p, lf, cmd = start(arm, model, port, gpus, node)
            servers.append((arm, p, lf, port))
            log(f"{arm}: server starting on GPUs {gpus}, NUMA node {node}, port {port}")
            emit({"stage": "server", "arm": arm, "cmd": cmd, "gpus": gpus, "node": node})

        t0 = time.time()
        for arm, p, lf, port in servers:
            if not healthy(p, port):
                raise Abort(f"{arm}: server did not come up")
            slog = os.path.join(W, f"server_{arm}.log")
            kv = kv_types(slog)
            if [t for t in kv if t != "f16"]:
                raise Abort(f"{arm}: KV types {kv} are not all f16")
            said = chat(port, "What is 17 × 23? Reply with only the number.")
            ok = "391" in said
            emit({"stage": "load", "arm": arm, "ok": True, "load_s": round(time.time() - t0, 1),
                  "kv_types": kv, "coherent": ok, "said": said[:200], "gpu": gpu_mib()})
            log(f"{arm}: up in {time.time() - t0:.0f}s, KV {kv}, 17x23 -> {said[:40]!r}")
            if not ok:
                raise Abort(f"{arm}: 17 x 23 came back as {said[:80]!r}")

        runs = []
        for arm, _, _, port in servers:
            node = dict((a[0], a[4]) for a in ARMS)[arm]
            env = {**os.environ,
                   "HEP_ENDPOINT": f"http://127.0.0.1:{port}/v1/chat/completions",
                   "HEP_MODEL": arm, "HEP_TEMP": "0", "HEP_K": "1", "HEP_MAXTOK": "4096",
                   "HEP_THINK": "0", "HEP_PREFIX": "usable", "HEP_TAG": arm}
            out = open(os.path.join(W, f"hep_{arm}.log"), "w")
            cmd = ["numactl", f"--cpunodebind={node}", f"--membind={node}", "python3", "-u", HEP]
            runs.append((arm, subprocess.Popen(cmd, cwd=W, stdout=out, stderr=subprocess.STDOUT, env=env), out))
            log(f"{arm}: HumanEval+ started (node {node}) -> hep_{arm}.log")
            emit({"stage": "hep_start", "arm": arm, "cmd": cmd, "env": {k: v for k, v in env.items()
                                                                        if k.startswith("HEP_")}})

        for arm, p, out in runs:
            rc = p.wait()
            out.close()
            tail = open(os.path.join(W, f"hep_{arm}.log"), errors="replace").read()[-4000:]
            m = re.search(r"SIGNAL: \S+ \S+ done \(pooled ([\d.]+)%\)", tail)
            emit({"stage": "hep_done", "arm": arm, "rc": rc,
                  "pooled_pass_at_1": float(m.group(1)) if m else None, "tail": tail[-1500:]})
            log(f"{arm}: HumanEval+ exited rc={rc}" + (f", pooled {m.group(1)}%" if m else " (no SIGNAL line)"))
    except Exception as e:
        log(f"ABORT: {type(e).__name__}: {e}")
        emit({"stage": "abort", "msg": f"{type(e).__name__}: {e}"})
        sys.exit(1)
    finally:
        for arm, p, lf, port in servers:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(90)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            lf.close()
        for _ in range(120):
            if all(m < 500 for m in gpu_mib()):
                break
            time.sleep(1)
    log("=== TEST 11 COMPLETE ===")


if __name__ == "__main__":
    main()
