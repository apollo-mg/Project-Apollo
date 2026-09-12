#!/usr/bin/env python3
"""Driver for PREREG_EXL3_KLD.md (EXL3 campaign, test 3). Runs ON .73, with the wake proxy PAUSED.

Preflight re-hashes every GGUF copied for this test against its published LFS sha256, size-checks the
weights hash-verified on .73 earlier today, and refuses to start if a llama process runs, either GPU
holds memory, or a reference file already exists. The reference run writes ref.kld; every other run
is scored against it. Each run's row is appended, flushed and fsynced.

Usage (on .73):  python3 exl3_kld.py ALL
"""
import json, os, re, subprocess, sys, time

BIN = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin/llama-perplexity")   # 9ae8f0f40 + e8m0 guard
OUT = os.path.expanduser("~/exl3_kld")
RES = os.path.join(OUT, "results.jsonl")
KDIR = "/mnt/HDD/kld"
BASE = os.path.join(KDIR, "ref.kld")
TXT, TXT_SHA = "/mnt/HDD/exl3/wiki.test.raw", "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"
EXL3 = "/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw"
EXL3_SAFETENSORS_BYTES = 16860809795          # shards hash-verified on .73 in RESULT_EXL3_SM60_INFERENCE.md
Q6K, Q6K_BYTES = "/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf", 22884408288   # hash-verified on .73 today
Q8 = f"{KDIR}/Qwen3.8-27B-Q8_0.gguf"
IQ4 = f"{KDIR}/Qwen3.8-27B-UD-IQ4_XS.gguf"
Q4KM = f"{KDIR}/Qwen3.8-27B-UD-Q4_K_M.gguf"
COPIED = {   # unsloth/Qwen3.8-27B-GGUF @ 4ca720788d1e01f1bff70c033e0d0028fd02e502: bytes, published LFS sha256
    Q8: (29047086048, "a680f44a06920e5d689774823782006aa3acc8db95750323373b24139b67e348"),
    IQ4: (14252845984, "40fac4050e940397dbf13087afd50f4734a11805bf9d65ef8ddd7483470e6199"),
    Q4KM: (16464440224, "322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482"),
}
ARMS = [("REF", Q8), ("R2", Q8), ("E", EXL3), ("G4", IQ4), ("G5", Q4KM), ("G6", Q6K)]
FLAGS = ["-ngl", "99", "-sm", "layer", "-c", "512", "-b", "512", "-ub", "8", "--chunks", "40",
         "-fa", "on", "-ctk", "f16", "-ctv", "f16"]
NUM = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
PATTERNS = {   # llama-perplexity's own summary lines (tools/perplexity/perplexity.cpp @ 9ae8f0f40)
    ("kld_mean", "kld_err"): rf"Mean\s+KLD:\s+{NUM}\s+±\s+{NUM}",
    ("kld_median",): rf"Median\s+KLD:\s+{NUM}",
    ("kld_p99",): rf"99\.0%\s+KLD:\s+{NUM}",
    ("kld_max",): rf"Maximum KLD:\s+{NUM}",
    ("same_top", "same_top_err"): rf"Same top p:\s+{NUM}\s+±\s+{NUM}",
    ("ppl_q", "ppl_q_err"): rf"Mean PPL\(Q\)\s+:\s+{NUM}\s+±\s+{NUM}",
    ("ppl_final", "ppl_final_err"): rf"Final estimate: PPL = {NUM} \+/- {NUM}",
}


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "kld.log"), "a") as f:
        f.write(line + "\n")


def emit(row):
    row["ts"] = time.strftime("%F %T")
    with open(RES, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())


def gpu_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split()]


def sha256(path):
    return subprocess.run(["sha256sum", path], capture_output=True, text=True, check=True).stdout.split()[0]


def disk_bytes(path):
    if os.path.isdir(path):
        return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)
    return os.path.getsize(path)


def preflight():
    if not os.path.exists(BIN):
        sys.exit(f"PREFLIGHT: missing {BIN}")
    if os.path.exists(BASE):
        sys.exit(f"PREFLIGHT: {BASE} already exists -- refusing to reuse or overwrite a reference")
    if sha256(TXT) != TXT_SHA:
        sys.exit(f"PREFLIGHT: {TXT} does not match its recorded sha256")
    for path, (size, want) in COPIED.items():
        if not os.path.exists(path) or os.path.getsize(path) != size:
            sys.exit(f"PREFLIGHT: {path} missing or wrong size")
        t0 = time.time()
        got = sha256(path)
        if got != want:
            sys.exit(f"PREFLIGHT: {path} sha256 {got} != published {want}")
        log(f"verified {os.path.basename(path)} against its published sha256 ({time.time() - t0:.0f} s)")
    st = sum(os.path.getsize(os.path.join(EXL3, f)) for f in os.listdir(EXL3) if f.endswith(".safetensors"))
    if st != EXL3_SAFETENSORS_BYTES:
        sys.exit(f"PREFLIGHT: EXL3 safetensors total {st} != {EXL3_SAFETENSORS_BYTES}")
    if os.path.getsize(Q6K) != Q6K_BYTES:
        sys.exit(f"PREFLIGHT: {Q6K} is not {Q6K_BYTES} bytes")
    for name in ("llama-server", "llama-perplexity"):
        busy = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True).stdout.split()
        if busy:
            sys.exit(f"PREFLIGHT: {name} already running (pids {busy})")
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB -- refusing to share them")
    log(f"preflight ok: GPUs {gpu_mib()} MiB; size checks passed for EXL3 and Q6_K")


def run(label, model):
    extra = ["--kl-divergence-base", BASE] + ([] if label == "REF" else ["--kl-divergence"])
    cmd = [BIN, "-m", model, "-f", TXT, *FLAGS, *extra]
    logpath = os.path.join(OUT, f"ppl_{label}.log")
    log(f"=== {label}: {os.path.basename(model)}")
    t0, peak, timed_out = time.time(), [0] * len(gpu_mib()), False
    with open(logpath, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        while p.poll() is None:
            if time.time() - t0 > 3600:
                p.kill()
                p.wait()
                timed_out = True
                break
            peak = [max(a, b) for a, b in zip(peak, gpu_mib())]
            time.sleep(2)
    with open(logpath, encoding="utf-8", errors="replace") as f:
        text = f.read()
    row = {"arm": label, "model": model, "flags": FLAGS, "stage": "run", "rc": p.returncode,
           "timed_out": timed_out, "wall_s": round(time.time() - t0, 1), "peak_mib": peak,
           "disk_bytes": disk_bytes(model), "failed_decode": "failed to decode" in text}
    for keys, pattern in PATTERNS.items():
        m = re.search(pattern, text)
        for i, k in enumerate(keys):
            row[k] = float(m.group(i + 1)) if m else None
    if label == "REF":
        row["base_bytes"] = os.path.getsize(BASE) if os.path.exists(BASE) else None
    emit(row)
    log(f"  rc={p.returncode} {row['wall_s']:.0f}s peak={peak} KLD={row['kld_mean']} top={row['same_top']} "
        f"PPL={row['ppl_final'] or row['ppl_q']}")
    return row


def main():
    os.makedirs(OUT, exist_ok=True)
    preflight()
    v = subprocess.run([BIN, "--version"], capture_output=True, text=True)
    emit({"stage": "meta", "bin": BIN, "version": (v.stdout + v.stderr).strip()[-240:]})
    ref = run("REF", Q8)
    if ref["rc"] != 0 or not ref.get("base_bytes") or ref["failed_decode"]:
        log("REF did not produce a usable reference -- stopping; every prediction is VOID")
        return
    for label, model in ARMS[1:]:
        run(label, model)
    log("=== DONE ===")


if __name__ == "__main__":
    main()
