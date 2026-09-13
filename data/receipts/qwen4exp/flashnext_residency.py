#!/usr/bin/env python3
"""Driver for PREREG_FLASHNEXT_RESIDENCY.md. Runs ON .194, launched detached.

Stage 1 (default):  gates -> host-bandwidth triad -> the GGUF llama-server arms.
Stage 2 (--stage2): gates -> EXL3 snapshot verified against its manifest -> the F-X3 arm.
Stage 3 (--stage3): gates -> IQ4_XS with its overflow spilled as experts, then the auto-fit retest.
One JSONL row per measurement, flushed and fsynced; an arm with an "arm_done" row is skipped on restart.
Checks ABORT the run -- they never print a warning and carry on.

Stage 1 ran from this file at sha 3699e75d. Later revisions add the EXL3 arm, a directory model path, manifest
verification, a longer load limit, full timings per request, an abort if speculative decoding ever runs, and the
Stage 3 arms with a per-arm -fit override; none of it changes a Stage 1 arm or Stage 2's arm definition.

Stage 4 (--stage4): gates -> the expert-spill cost ladder, -ncmoe {2,4,8,16,32,48} under --numa distribute.

Usage (on .194):  python3 flashnext_residency.py [--stage2 | --stage3 | --stage3b | --stage4]
"""
import hashlib, json, os, re, subprocess, sys, threading, time, urllib.request

H = os.path.expanduser("~")
OUT = os.path.join(H, "flashnext_res")
RES = os.path.join(OUT, "results.jsonl")
BIN = os.path.join(H, "buun-c7f114d34/build_sm60/bin/llama-server")
COMMIT = "c7f114d34"
BUILD_LOG = os.path.join(H, "build_c7f114d34.log")
HASHES = os.path.join(H, "flashnext_sha256.txt")
MODELS = os.path.join(H, "AI/Models")
PUBLISHED = os.path.join(OUT, "published_sha256.json")
WIKI = os.path.join(OUT, "wiki.test.raw")
WIKI_SHA = "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"
PORT = 8093
COMMON = ["-c", "4096", "-np", "1", "-b", "2048", "-ub", "512", "-fa", "on", "--jinja", "-fit", "off",
          "-sm", "layer", "-ctk", "f16", "-ctv", "f16", "--host", "127.0.0.1", "--port", str(PORT)]
ENV = {**os.environ, "GGML_CUDA_ALLREDUCE": "internal", "CUDA_VISIBLE_DEVICES": "0,1,2,3"}
LENGTHS, REPS, N_PREDICT = (500, 1800, 3600), 3, 128
Q2 = "flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL"
IQ4 = "flashnext/Qwen3.8-Flash-Next-UD-IQ4_XS"
IQ1 = "flashnext_iq1s/Qwen3.8-Flash-Next-UD-IQ1_S"
EXPS_44_47 = r"blk\.(44|45|46|47)\.ffn_(up|down|gate)_exps=CPU"
ARMS = [
    ("F-Q2", Q2, ["-ngl", "99"]),
    ("P-Q2", Q2, ["-ngl", "44"]),
    ("X-Q2", Q2, ["-ngl", "99", "-ot", EXPS_44_47]),
    ("P-IQ4", IQ4, ["-ngl", "44"]),
    ("P-IQ4-numa", IQ4, ["-ngl", "44", "--numa", "distribute"]),
    ("P-IQ4-b", IQ4, ["-ngl", "44"]),
]
FALLBACK = ("F-IQ1", IQ1, ["-ngl", "99"])   # declared in the prereg: replaces F-Q2 only if it fails to load
# Stage 2: turboderp 3.05bpw_h5_ng5 at 69e33439, a snapshot DIRECTORY; -sm layer (32c2c1479 rejects
# multi-device EXL3 tensor split). The manifest comes from hf_fetch's verified copy on the control plane.
EXL3 = os.path.join(MODELS, "exl3/Qwen3.8-Flash-Next-exl3-3.05bpw_h5_ng5")
EXL3_MANIFEST = os.path.join(OUT, "manifest_F-X3.txt")
STAGE2 = [("F-X3", EXL3, ["-ngl", "99"])]
# Stage 3 (Amendment 3): -ncmoe N spills the experts of the first N layers, which sit on card 0 -- the card that
# overflowed. S3-X4n4 runs only if S3-X4 fails to load. S3-FIT swaps the common "-fit off" for "-fit on".
STAGE3 = [("S3-X4", IQ4, ["-ngl", "99", "-ncmoe", "2"]),
          ("S3-FIT", IQ4, ["-ngl", "99", "-fit", "on"])]
STAGE3_FALLBACK = ("S3-X4n4", IQ4, ["-ngl", "99", "-ncmoe", "4"])
# Stage 3b (Amendment 5): the auto-fit retest as it should have been specified -- no user -ngl, so fit may choose
# the placement itself. S3-FIT pinned -ngl 99, and fit declines to act on a user-set n_gpu_layers.
STAGE3B = [("S3-FIT2", IQ4, ["-fit", "on"])]
# Stage 4 (PREREG_FLASHNEXT_SPILL_LADDER.md): the expert-spill cost curve. Six geometric rungs of -ncmoe on
# IQ4_XS, every one under --numa distribute -- -ncmoe puts expert tensors on the CPU backend, so the binding
# resource is host memory bandwidth, and Stage 1 measured node-local 22.68 GB/s against cross-socket 7.00.
# Unpinned, a slope that misses the cost model could be bandwidth or placement, with no way to tell.
# n_layer = 48 (verify/load_P-IQ4.log: block_count 48), so rung 48 is every layer's experts on the host.
# -lv 4 on every rung so the f16 KV assertion has lines to inspect: the vacuous-guard defect, third occurrence.
NCMOE_RUNGS = (2, 4, 8, 16, 32, 48)
STAGE4 = [(f"L-{n:02d}", IQ4, ["-ngl", "99", "-ncmoe", str(n), "--numa", "distribute", "-lv", "4"])
          for n in NCMOE_RUNGS]


class Abort(Exception):
    pass


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "driver.log"), "a") as f:
        f.write(line + "\n")


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def rows():
    if not os.path.exists(RES):
        return []
    with open(RES) as f:
        return [json.loads(l) for l in f if l.strip()]


def shards(stem):
    return [f"{stem}-0000{i}-of-00003.gguf" for i in (1, 2, 3)]


def model_path(stem):
    """A snapshot directory loads as itself; a GGUF stem loads from its first shard."""
    return stem if os.path.isdir(stem) else os.path.join(MODELS, shards(stem)[0])


def common_for(flags):
    """An arm that sets -fit itself replaces the common '-fit off' (Stage 3's auto-fit retest)."""
    if "-fit" not in flags:
        return COMMON
    i = COMMON.index("-fit")
    return COMMON[:i] + COMMON[i + 2:]


def sha256(path):
    return subprocess.run(["sha256sum", path], capture_output=True, text=True, check=True).stdout.split()[0]


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def heavy():
    """Anything that would contend for memory bandwidth, disk or the GPUs during a measurement."""
    names = {"cmake", "make", "gmake", "ninja", "nvcc", "cicc", "ptxas", "cc1plus", "sha256sum", "llama-server",
             "rsync", "ctest"}
    comms = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout.split()
    return sorted({c for c in comms if c in names})


def verify(stems, have):
    with open(PUBLISHED) as f:
        pub = json.load(f)
    for stem in stems:
        for rel in shards(stem):
            want = pub.get(rel)
            if not want:
                raise Abort(f"no published sha256 recorded for {rel}")
            got = have.get(rel) or sha256(os.path.join(MODELS, rel))
            if got != want:
                raise Abort(f"{rel}: sha256 {got} != published {want}")


def verify_manifest(path):
    """Stage 2: every file of the EXL3 snapshot against the manifest from the verified control-plane copy."""
    if not os.path.exists(path):
        raise Abort(f"no manifest at {path}")
    n = 0
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            want, rel = line.split(maxsplit=1)
            rel = rel.strip()
            got = sha256(os.path.join(EXL3, rel))
            if got != want:
                raise Abort(f"{rel}: sha256 {got} != manifest {want}")
            n += 1
    if n == 0:
        raise Abort(f"manifest {path} lists no files")
    return n


def gates():
    text = open(BUILD_LOG, errors="replace").read() if os.path.exists(BUILD_LOG) else ""
    if "BUILD EXIT 0" not in text:
        raise Abort(f"the {COMMIT} build has not finished with BUILD EXIT 0")
    v = subprocess.run([BIN, "--version"], capture_output=True, text=True, env=ENV)
    ver = (v.stdout + v.stderr).strip()
    if COMMIT not in ver:
        raise Abort(f"llama-server --version does not report {COMMIT}: {ver[:200]}")
    htxt = open(HASHES).read() if os.path.exists(HASHES) else ""
    if "HASHING-DONE" not in htxt:
        raise Abort("weight hashing has not finished")
    have = {p[1]: p[0] for p in (l.split() for l in htxt.splitlines()) if len(p) == 2}
    verify([Q2, IQ4], have)
    if sha256(WIKI) != WIKI_SHA:
        raise Abort("wikitext does not match its recorded sha256")
    if any(m > 500 for m in gpu_mib()):
        raise Abort(f"GPUs not empty: {gpu_mib()} MiB")
    if heavy():
        raise Abort(f"other heavy processes are running: {heavy()}")
    clk = subprocess.run(["nvidia-smi", "--query-gpu=index,clocks.applications.graphics,power.limit",
                          "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    return ver, clk


def bandwidth():
    if any(r.get("stage") == "bw" for r in rows()):
        log("bandwidth already measured -- skipping")
        return
    exe = os.path.join(OUT, "membw")
    subprocess.run(["gcc", "-O3", "-march=native", "-fopenmp", os.path.join(OUT, "membw.c"), "-o", exe],
                   check=True)
    one = {"OMP_NUM_THREADS": "10", "OMP_PROC_BIND": "close", "OMP_PLACES": "cores"}
    two = {"OMP_NUM_THREADS": "20", "OMP_PROC_BIND": "spread", "OMP_PLACES": "cores"}
    for label, env, pre in (
        ("B-L0", one, ["numactl", "--cpunodebind=0", "--membind=0"]),
        ("B-L1", one, ["numactl", "--cpunodebind=1", "--membind=1"]),
        ("B-R01", one, ["numactl", "--cpunodebind=0", "--membind=1"]),
        ("B-IL", two, ["numactl", "--interleave=all"]),
        ("B-FT", two, []),
    ):
        p = subprocess.run(pre + [exe, str(1 << 27), "10"], capture_output=True, text=True,
                           env={**os.environ, **env}, timeout=600)
        m = re.search(r"best_triad_GBps=([\d.]+)", p.stdout)
        emit({"stage": "bw", "arm": label, "rc": p.returncode, "gbps": float(m.group(1)) if m else None,
              "env": env, "numactl": pre, "stdout": p.stdout.strip()})
        log(f"{label}: {p.stdout.strip()}")


def drop_caches():
    return subprocess.run(["sudo", "-n", "sh", "-c", "sync; echo 3 > /proc/sys/vm/drop_caches"],
                          capture_output=True).returncode == 0


def http(path, payload=None, timeout=1200):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def healthy(p, limit=3600):
    # 3600 s: the 27B EXL3 took 318 s to load on .73, and the Flash-Next snapshot is ~6x larger
    t0 = time.time()
    while time.time() - t0 < limit:
        if p.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


class Peak(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.halt = [0] * len(gpu_mib()), threading.Event()

    def run(self):
        while not self.halt.is_set():
            self.peak = [max(a, b) for a, b in zip(self.peak, gpu_mib())]
            self.halt.wait(2)


def parse_log(text):
    bufs = {}
    for m in re.finditer(r"(\S+) model buffer size\s*=\s*([\d.]+) MiB", text):
        bufs[m.group(1)] = round(bufs.get(m.group(1), 0.0) + float(m.group(2)), 2)   # one line per shard
    off = re.search(r"offloaded (\d+)/(\d+) layers to GPU", text)
    thr = re.search(r"n_threads\s*=\s*(\d+)", text)
    return {"model_buffers_mib": bufs, "kv_types": sorted(set(re.findall(r"\b[KV] \((\w+)\)", text))),
            "offloaded": f"{off.group(1)}/{off.group(2)}" if off else None,
            "n_threads": int(thr.group(1)) if thr else None}


def run_arm(label, stem, flags):
    caches = drop_caches()
    logpath = os.path.join(OUT, f"server_{label}.log")
    cmd = [BIN, "-m", model_path(stem), *common_for(flags), *flags]
    log(f"=== {label}: {' '.join(flags)}  (page cache dropped: {caches})")
    t0 = time.time()
    lf = open(logpath, "w")
    p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=ENV)
    peak = Peak()
    peak.start()
    try:
        ok = healthy(p)
        text = open(logpath, errors="replace").read()
        info = parse_log(text)
        base = {"arm": label, "model": stem, "flags": flags, "caches_dropped": caches, **info}
        if not ok:
            emit({"stage": "load", "ok": False, "load_s": round(time.time() - t0, 1), **base,
                  "tail": text[-4000:], "cmd": cmd})
            log(f"{label}: server did not come up -- recorded")
            return False
        if "-lv" in flags:
            # A rung that asked for -lv 4 MUST show its KV lines. An empty list here means the check is
            # vacuous, which is the defect this stage exists not to repeat -- so empty is a failure, not a pass.
            if info["kv_types"] != ["f16"]:
                raise Abort(f"{label}: KV types {info['kv_types']} are not exactly ['f16'] "
                            f"(empty = the guard found nothing to inspect despite -lv 4)")
        elif [t for t in info["kv_types"] if t != "f16"]:
            raise Abort(f"{label}: KV cache types {info['kv_types']} are not all f16")
        emit({"stage": "load", "ok": True, "load_s": round(time.time() - t0, 1), **base,
              "gpu_after_load": gpu_mib(), "cmd": cmd})

        r = http("/v1/chat/completions", {
            "messages": [{"role": "user", "content": "What is 17 × 23? Reply with only the number."}],
            "max_tokens": 512, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}},
            timeout=900)
        msg = r["choices"][0]["message"]
        said = (msg.get("content") or "") + (msg.get("reasoning_content") or "")
        emit({"stage": "coherence", "arm": label, "ok": "391" in said, "said": said[:300]})
        if "391" not in said:
            raise Abort(f"{label}: 17 x 23 came back as {said[:80]!r}")

        with open(WIKI, encoding="utf-8") as f:
            ids = http("/tokenize", {"content": f.read()[:60000]})["tokens"]
        if len(ids) < max(LENGTHS):
            raise Abort(f"wikitext slice tokenized to only {len(ids)} tokens")
        http("/completion", {"prompt": ids[:64], "n_predict": 8, "cache_prompt": False, "temperature": 0})
        for n in LENGTHS:
            for rep in range(REPS):
                prompt = ids[:n]
                r = http("/completion", {"prompt": prompt, "n_predict": N_PREDICT, "cache_prompt": False,
                                         "temperature": 0, "ignore_eos": True})
                t = r.get("timings") or {}
                emit({"stage": "req", "arm": label, "len": n, "rep": rep,
                      "prompt_sha": hashlib.sha256(json.dumps(prompt).encode()).hexdigest()[:16],
                      "prompt_n": t.get("prompt_n"), "pp_tps": t.get("prompt_per_second"),
                      "predicted_n": t.get("predicted_n"), "tg_tps": t.get("predicted_per_second"),
                      "prompt_ms": t.get("prompt_ms"), "predicted_ms": t.get("predicted_ms"), "timings": t})
                if t.get("draft_n"):
                    raise Abort(f"{label}: speculative decoding ran (draft_n={t.get('draft_n')}); "
                                "the prereg runs every arm without it")
                log(f"{label} len={n} rep={rep}: pp {t.get('prompt_per_second') or 0:.1f}  "
                    f"tg {t.get('predicted_per_second') or 0:.2f} tok/s")
        emit({"stage": "arm_done", "arm": label, "peak_mib": peak.peak, "wall_s": round(time.time() - t0, 1)})
        return True
    finally:
        peak.halt.set()
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


def main():
    os.makedirs(OUT, exist_ok=True)
    stage = ("3b" if "--stage3b" in sys.argv else 4 if "--stage4" in sys.argv
             else 3 if "--stage3" in sys.argv else 2 if "--stage2" in sys.argv else 1)
    try:
        ver, clk = gates()
        emit({"stage": "gates", "ok": True, "version": ver[:300], "clocks": clk, "run_stage": stage})
        log(f"gates passed (stage {stage}) -- {ver.splitlines()[0] if ver else ''}")
        if stage == 2:
            t0 = time.time()
            n = verify_manifest(EXL3_MANIFEST)
            log(f"EXL3 snapshot: {n} files verified against its manifest in {time.time() - t0:.0f} s")
            queue = list(STAGE2)
        elif stage == 3:
            queue = list(STAGE3)
        elif stage == "3b":
            queue = list(STAGE3B)
        elif stage == 4:
            queue = list(STAGE4)
        else:
            bandwidth()
            queue = list(ARMS)
        done = {r["arm"] for r in rows() if r.get("stage") == "arm_done"}
        while queue:
            label, stem, flags = queue.pop(0)
            if label in done:
                log(f"{label} already complete -- skipping")
                continue
            loaded = run_arm(label, stem, flags)
            if not loaded and label == "F-Q2":
                log("F-Q2 did not load -- verifying and running the declared fallback F-IQ1")
                verify([IQ1], {})
                queue.insert(0, FALLBACK)
            if not loaded and label == "S3-X4":
                log("S3-X4 did not load at -ncmoe 2 -- running the declared fallback S3-X4n4")
                queue.insert(0, STAGE3_FALLBACK)
    except Exception as e:   # Abort, or anything unexpected: record it, never limp on
        log(f"ABORT: {type(e).__name__}: {e}")
        emit({"stage": "abort", "msg": f"{type(e).__name__}: {e}"})
        sys.exit(1)
    log(f"=== STAGE {stage} COMPLETE ===")


if __name__ == "__main__":
    main()
