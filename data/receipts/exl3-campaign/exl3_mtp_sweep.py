#!/usr/bin/env python3
"""Driver for PREREG_EXL3_MTP_SWEEP.md (EXL3 campaign, test 4). Runs ON .73, wake proxy PAUSED.

One llama-bench process per weights format: the model loads once and every micro-batch size reuses it,
so t/s(pp64) against n_ubatch reads directly how a matmul's cost scales with rows. Every row is
appended, flushed and fsynced as it is produced.

Usage (on .73):  python3 exl3_mtp_sweep.py ALL
"""
import json, os, subprocess, sys, time

BENCH = os.path.expanduser("~/buun-sm60-qual/build_sm60qual/bin/llama-bench")   # 9ae8f0f40 + e8m0 guard
OUT = os.path.expanduser("~/exl3_mtp")
RES = os.path.join(OUT, "results.jsonl")
EXL3 = "/mnt/HDD/exl3/Qwen3.8-27B-exl3-4.00bpw"
EXL3_SAFETENSORS_BYTES = 16860809795          # shards hash-verified on .73 in RESULT_EXL3_SM60_INFERENCE.md
Q6K, Q6K_BYTES = "/mnt/models/AI_Models/Qwen 3.8/Qwen3.8-27B-Q6_K.gguf", 22884408288
MODELS = [("X", EXL3), ("Q", Q6K)]
# Amendment 1: ub 1 runs twice. The first test after a load is cold -- on the first attempt EXL3's tg8
# read 5.42 t/s at ub1 against 6.95 everywhere after (28.5% spread, control failed), which also
# depressed the pp64 ub1 baseline that every A(m) divides by. The trailing repeat gives a warm baseline.
ARGS = ["-ngl", "99", "-sm", "layer", "-fa", "on", "-ctk", "f16", "-ctv", "f16",
        "-p", "64", "-n", "8", "-ub", "1,2,4,8,16,1", "-r", "3", "-o", "json"]
KEEP = ("n_prompt", "n_gen", "n_ubatch", "n_batch", "avg_ts", "stddev_ts", "samples_ts",
        "build_commit", "split_mode", "type_k", "type_v", "flash_attn", "model_type", "model_size")


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(os.path.join(OUT, "mtp.log"), "a") as f:
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


def preflight():
    if not os.path.exists(BENCH):
        sys.exit(f"PREFLIGHT: missing {BENCH}")
    st = sum(os.path.getsize(os.path.join(EXL3, f)) for f in os.listdir(EXL3) if f.endswith(".safetensors"))
    if st != EXL3_SAFETENSORS_BYTES:
        sys.exit(f"PREFLIGHT: EXL3 safetensors total {st} != {EXL3_SAFETENSORS_BYTES}")
    if os.path.getsize(Q6K) != Q6K_BYTES:
        sys.exit(f"PREFLIGHT: {Q6K} is not {Q6K_BYTES} bytes")
    busy = subprocess.run(["pgrep", "-x", "llama-server"], capture_output=True, text=True).stdout.split()
    if busy:
        sys.exit(f"PREFLIGHT: llama-server running (pids {busy}) -- is the wake proxy paused?")
    # `pgrep -x llama-perplexity` cannot match (pgrep -x compares the 15-char process name), so the
    # GPU-memory check below is the guard that actually catches a busy node.
    if any(m > 500 for m in gpu_mib()):
        sys.exit(f"PREFLIGHT: GPUs not empty {gpu_mib()} MiB -- refusing to share them")
    log(f"preflight ok: GPUs {gpu_mib()} MiB")


def run(label, model):
    log(f"=== {label}: {os.path.basename(model)}")
    t0 = time.time()
    p = subprocess.run([BENCH, "-m", model, *ARGS], capture_output=True, text=True, timeout=5400)
    with open(os.path.join(OUT, f"bench_{label}.json"), "w") as f:
        f.write(p.stdout)
    with open(os.path.join(OUT, f"bench_{label}.err"), "w") as f:
        f.write(p.stderr)
    wall = round(time.time() - t0, 1)
    try:
        entries = json.loads(p.stdout)
    except Exception as e:
        emit({"arm": label, "stage": "error", "rc": p.returncode, "wall_s": wall, "error": repr(e),
              "stderr_tail": p.stderr[-800:]})
        log(f"  FAILED rc={p.returncode}: {e!r}")
        return
    commit = entries[0].get("build_commit") if entries else None
    if not commit or not str(commit).startswith("9ae8f0f4"):
        emit({"arm": label, "stage": "error", "rc": p.returncode, "wall_s": wall,
              "error": f"llama-bench reports build_commit {commit!r}, not 9ae8f0f4"})
        sys.exit(f"ABORT: llama-bench reports build_commit {commit!r}, not 9ae8f0f4")
    for e in entries:
        emit({"arm": label, "stage": "bench", "model": model, **{k: e.get(k) for k in KEEP}})
    emit({"arm": label, "stage": "done", "rc": p.returncode, "wall_s": wall, "entries": len(entries)})
    for e in entries:
        kind = f"pp{e['n_prompt']}" if e.get("n_prompt") else f"tg{e['n_gen']}"
        log(f"  ub {e['n_ubatch']:>3} {kind:>6}: {e['avg_ts']:.2f} ± {e['stddev_ts']:.2f} t/s")


def main():
    os.makedirs(OUT, exist_ok=True)
    preflight()
    v = subprocess.run([BENCH, "--version"], capture_output=True, text=True)
    emit({"stage": "meta", "bin": BENCH, "version": (v.stdout + v.stderr).strip()[-240:], "args": ARGS})
    for label, model in MODELS:
        run(label, model)
    log("=== DONE ===")


if __name__ == "__main__":
    main()
