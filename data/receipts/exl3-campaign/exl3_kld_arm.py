#!/usr/bin/env python3
"""Run ONE extra KLD arm against the reference test 3 already wrote (PREREG_EXL3_KLD.md, Amendment 2).

Runs ON .73 with the wake proxy PAUSED. Verifies every file of the model against a manifest of sha256
sums computed on the control plane (the copy there was verified against HF's published sums by
tools/hf_fetch.py), then scores the arm against the existing ref.kld and APPENDS to the same
results.jsonl, so tools/score_exl3_kld.py sees every arm together.

Usage (on .73):  python3 exl3_kld_arm.py <label> <model dir or file> <manifest>
  manifest lines: "<sha256>  <basename>"
"""
import json, os, re, subprocess, sys, time

BIN = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin/llama-perplexity")
OUT = os.path.expanduser("~/exl3_kld")
RES = os.path.join(OUT, "results.jsonl")
BASE = "/mnt/HDD/kld/ref.kld"
TXT, TXT_SHA = "/mnt/HDD/exl3/wiki.test.raw", "173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08"
FLAGS = ["-ngl", "99", "-sm", "layer", "-c", "512", "-b", "512", "-ub", "8", "--chunks", "40",
         "-fa", "on", "-ctk", "f16", "-ctv", "f16"]
NUM = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
PATTERNS = {
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


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    label, model, manifest = sys.argv[1:4]
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(BIN):
        sys.exit(f"PREFLIGHT: missing {BIN}")
    if not os.path.exists(BASE):
        sys.exit(f"PREFLIGHT: no reference at {BASE} -- test 3's REF arm must have written it")
    if sha256(TXT) != TXT_SHA:
        sys.exit("PREFLIGHT: wikitext does not match its recorded sha256")
    # `pgrep -x llama-perplexity` cannot match (comm truncates at 15 chars); check the GPUs instead.
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB")
    t0 = time.time()
    for line in open(manifest):
        want, name = line.split()
        path = os.path.join(model, name) if os.path.isdir(model) else model
        got = sha256(path)
        if got != want:
            sys.exit(f"PREFLIGHT: {path} sha256 {got} != {want} from the manifest")
    log(f"verified {label} against the control plane's manifest ({time.time() - t0:.0f} s)")

    cmd = [BIN, "-m", model, "-f", TXT, *FLAGS, "--kl-divergence-base", BASE, "--kl-divergence"]
    logpath = os.path.join(OUT, f"ppl_{label}.log")
    log(f"=== {label}: {os.path.basename(model)}")
    t0, peak = time.time(), [0] * len(gpu_mib())
    with open(logpath, "w") as lf:
        p = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        while p.poll() is None:
            if time.time() - t0 > 5400:
                p.kill()
                p.wait()
                break
            peak = [max(a, b) for a, b in zip(peak, gpu_mib())]
            time.sleep(2)
    with open(logpath, encoding="utf-8", errors="replace") as f:
        text = f.read()
    disk = (sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(model) for f in fs)
            if os.path.isdir(model) else os.path.getsize(model))
    row = {"arm": label, "model": model, "flags": FLAGS, "stage": "run", "rc": p.returncode,
           "wall_s": round(time.time() - t0, 1), "peak_mib": peak, "disk_bytes": disk,
           "failed_decode": "failed to decode" in text}
    for keys, pattern in PATTERNS.items():
        m = re.search(pattern, text)
        for i, k in enumerate(keys):
            row[k] = float(m.group(i + 1)) if m else None
    emit(row)
    log(f"  rc={p.returncode} {row['wall_s']:.0f}s peak={peak} KLD={row['kld_mean']} top={row['same_top']}")


if __name__ == "__main__":
    main()
