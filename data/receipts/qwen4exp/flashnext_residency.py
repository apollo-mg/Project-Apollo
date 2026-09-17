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

Usage (on .194):  python3 flashnext_residency.py
    [--stage2|--stage3|--stage3b|--stage4|--stage5a|--stage5b|--stage5c|--stage5d
     |--dimm-before|--dimm-after]
The dimm stages assert 1189 MHz / 250 W at the gate (a chassis reboot for the RAM swap reverts the
clock) and launch each spill rung three times for independent placement draws; see PREREG_DIMM_UPGRADE.md.
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
try:   # byte-exact identity of THIS driver, recorded in the gates row so the after-run can prove it
    DRIVER_SHA = hashlib.sha256(open(__file__, "rb").read()).hexdigest()   # reproduced the same code
except OSError:
    DRIVER_SHA = "?"
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
# Stage 5 (PREREG_FLASHNEXT_BREAK.md): Stage 4 bracketed the marginal-cost break with wide steps
# (8 -> 16 -> 32), so "the break is at 16" is a claim about an interval. Dense rungs resolve it, and every
# arm now captures per-node placement -- the measurement Stage 4 named as the reason its NUMA explanation
# stayed a hypothesis. Same BIN as Stage 4 (c7f114d34), so 8/16/32 are a replication check, not a bridge.
BASE5 = ["-ngl", "99", "--numa", "distribute", "-lv", "4"]
# 5a: the load-mode gate. mmap leaves spilled expert bytes as file-backed pages placed by first touch --
# which is what --numa distribute manipulates -- while dio reads into buffers placed by the allocating
# thread. Taking dio for its load-time win while measuring placement would confound P-B4 with the mode.
STAGE5A = [("M-mmap", IQ4, ["-ngl", "99", "-ncmoe", "16", "--numa", "distribute", "-lv", "4", "-lm", "mmap"]),
           ("M-dio", IQ4, ["-ngl", "99", "-ncmoe", "16", "--numa", "distribute", "-lv", "4", "-lm", "dio"])]
# Ordered so the three rungs Stage 4 shares (8, 16, 32) run FIRST: P-B7 decides whether anything else
# in this stage is interpretable, so it should not be waiting behind seven fill-in rungs. Resume is by
# arm_done, so order affects only what lands first, never correctness.
BREAK_RUNGS = (8, 16, 32, 10, 12, 14, 18, 20, 24, 28)
STAGE5B = [(f"D-{n:02d}", IQ4, ["-ncmoe", str(n)] + BASE5) for n in BREAK_RUNGS]
# Stage 5d (Amendment 3): the clock ladder. Identical flags to 5b -- the variable is system state, set
# externally to 1063 MHz / 150 W before this stage and recorded in the gates row. Rung 16 at that clock
# is already in hand from M-mmap, so only 8 and 32 are needed to complete the set.
STAGE5D = [(f"C-{n:02d}", IQ4, ["-ncmoe", str(n)] + BASE5) for n in (8, 32)]
# 5c (Amendment 6): --membind=0 replaces the original --interleave=all arm. 5b showed first touch is
# the only thing placing memory and that marginals are consequently uninterpretable, so the question is
# no longer "does a policy take effect" but "does pinning make the measurement reproducible". Interleave
# would deliberately put half the pages on the wrong socket for a shallow rung, where every consuming
# GPU is on node 0. B-16a/B-16b are the same configuration twice -- the run-to-run variance test that
# nothing in this campaign has ever done. B-08 asks whether pinning recovers D-08's -4.5 percent.
# Rung 16 needs 20,816 MiB against node 0's 31,772, so --membind=0 fits with headroom.
# --membind=0 ONLY. NOT --cpunodebind=0, which would cut the thread pool from 40 CPUs to node 0's 20
# and make these arms differ from their 5b controls in parallelism as well as memory policy.
# Paired with --numa distribute, identical to 5b: numactl sets the MEMORY policy, ggml sets THREAD
# affinity, and the two are orthogonal -- unlike interleave-vs-distribute, which would have been two
# placement strategies fighting. Memory policy is the only variable against D-16 and D-08.
MEMBIND0 = ["numactl", "--membind=0"]
STAGE5C = [("B-16a", IQ4, ["-ncmoe", "16"] + BASE5, MEMBIND0),
           ("B-16b", IQ4, ["-ncmoe", "16"] + BASE5, MEMBIND0),
           ("B-08", IQ4, ["-ncmoe", "8"] + BASE5, MEMBIND0)]
# DIMM baseline (PREREG_DIMM_UPGRADE.md, Amendment 3 + Amendment 4): the pre/post-upgrade "before"
# and "after". THE fork is P-D5, rung 48 (every layer's experts on the host), scored as a RATIO over
# the frozen 3-run before-median -- not against the old single-run 8.64@500, which is being replaced.
# Rung 48 needs both NUMA nodes to fit (PLE 27.5 GB + spilled experts > one node's 31.8 GB), so it
# CANNOT be --membind-pinned and inherits the first-touch placement lottery. A single launch cannot
# average that out, so each rung is launched DIMM_LAUNCHES times -- independent placement draws, not
# reps inside one launch (the scorer takes per-launch medians over reps 1..2, then the median and the
# full spread ACROSS launches; the spread is the only error bar the after-comparison will have).
# Rungs: 2 = control that fits VRAM entirely (P-D6, must not move); 16 = mid rung that separates the
# DDR4 bandwidth effect from the SATA page-cache confound; 48 = full spill (P-D5, the fork).
# Launch-major order so a kill leaves one COMPLETE draw of all three rungs rather than three of one.
DIMM_RUNGS = (2, 16, 48)
DIMM_LAUNCHES = 3
# The chassis is opened for the RAM swap -> host reboots -> GPU clock reverts to the 1063/150 boot
# default. An after-arm at the wrong clock is an ~8% decode confound on the fork, so gates() ASSERTS
# 1189 MHz / 250 W for both dimm stages and aborts with the set command if it reads anything else.
DIMM_CLOCK = (1189, 250)   # (applications.graphics MHz, power.limit W); mem clock 715, persistence on
def dimm_arms(prefix):
    return [(f"{prefix}-{n:02d}-L{k}", IQ4, ["-ncmoe", str(n)] + BASE5)
            for k in range(DIMM_LAUNCHES) for n in DIMM_RUNGS]
DIMM_BEFORE = dimm_arms("DB")   # run tonight at 1189/250 with 64 GB DDR4-2133, 8 DIMMs
DIMM_AFTER = dimm_arms("DA")    # run after the swap; same arms, same clock, verified from gates first


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


def parse_clocks(clk):
    # clk is the CSV from nvidia-smi --query-gpu=index,clocks.applications.graphics,power.limit
    out = []
    for line in clk.splitlines():
        m = re.search(r"(\d+)\s*MHz.*?([\d.]+)\s*W", line)
        if m:
            out.append((int(m.group(1)), float(m.group(2))))
    return out


def assert_clock(clk, want):
    mhz, watt = want
    got = parse_clocks(clk)
    setcmd = f"sudo nvidia-smi -pm 1 && sudo nvidia-smi -ac 715,{mhz} && sudo nvidia-smi -pl {watt}"
    if len(got) != 4:
        raise Abort(f"expected 4 GPU clock readings, parsed {len(got)} from {clk!r}")
    for i, (g, w) in enumerate(got):
        # P100 applications.graphics steps ~13 MHz; power.limit is set exactly. Tight tolerances so a
        # reboot-reverted 1063/150 (the confound this exists to catch) can never read as a pass.
        if abs(g - mhz) > 13 or abs(w - watt) > 2:
            raise Abort(f"GPU {i} reads {g} MHz / {w} W, not {mhz} MHz / {watt} W. A chassis reboot "
                        f"reverts to the 1063/150 boot default; the after-run must match the before-run. "
                        f"Set it and rerun:  {setcmd}")


def gates(require_clock=None):
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
    if require_clock is not None:
        assert_clock(clk, require_clock)   # aborts before any arm if the clock is not the required one
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


def numa_placement(pid):
    """Per-node resident pages for a live process, from /proc/<pid>/numa_maps.

    Stage 4 could not test its own NUMA explanation because nothing recorded placement. This is that
    measurement. Reported three ways because the load mode decides which one holds the expert bytes:
    under mmap they are file-backed pages, under dio they are anonymous buffers. The prereg's imbalance
    I is therefore defined on TOTAL pages, which is the only class-agnostic figure; anon and file are
    recorded alongside so a shift between classes is visible rather than silently changing what I means.
    """
    tot, anon, filed = {}, {}, {}
    try:
        with open(f"/proc/{pid}/numa_maps") as f:
            for line in f:
                parts = line.split()
                bucket = filed if any(p.startswith("file=") for p in parts) else anon
                for p in parts:
                    m = re.fullmatch(r"N(\d+)=(\d+)", p)
                    if m:
                        n, pages = int(m.group(1)), int(m.group(2))
                        tot[n] = tot.get(n, 0) + pages
                        bucket[n] = bucket.get(n, 0) + pages
    except (FileNotFoundError, ProcessLookupError, PermissionError) as e:
        return {"error": f"{type(e).__name__}: {e}"}
    if not tot:
        return {"error": "numa_maps yielded no N<node>= entries"}
    mib = lambda d: {str(k): round(v * 4096 / 2**20, 1) for k, v in sorted(d.items())}
    hi, lo = max(tot.values()), min(tot.values())
    return {"total_mib": mib(tot), "anon_mib": mib(anon), "file_mib": mib(filed),
            "nodes": len(tot), "imbalance": round((hi - lo) / (hi + lo), 4) if (hi + lo) else None}


def numastat(pid):
    p = subprocess.run(["numastat", "-p", str(pid)], capture_output=True, text=True)
    return p.stdout.strip()[-1500:] if p.returncode == 0 else f"rc={p.returncode}"


def parse_log(text):
    bufs = {}
    for m in re.finditer(r"(\S+) model buffer size\s*=\s*([\d.]+) MiB", text):
        bufs[m.group(1)] = round(bufs.get(m.group(1), 0.0) + float(m.group(2)), 2)   # one line per shard
    off = re.search(r"offloaded (\d+)/(\d+) layers to GPU", text)
    thr = re.search(r"n_threads\s*=\s*(\d+)", text)
    return {"model_buffers_mib": bufs, "kv_types": sorted(set(re.findall(r"\b[KV] \((\w+)\)", text))),
            "offloaded": f"{off.group(1)}/{off.group(2)}" if off else None,
            "n_threads": int(thr.group(1)) if thr else None}


def run_arm(label, stem, flags, pre=None):
    caches = drop_caches()
    logpath = os.path.join(OUT, f"server_{label}.log")
    cmd = list(pre or []) + [BIN, "-m", model_path(stem), *common_for(flags), *flags]
    log(f"=== {label}: {' '.join(list(pre or []) + flags)}  (page cache dropped: {caches})")
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
        # numactl execs in place, so p.pid is llama-server itself -- but verify rather than assume,
        # because reading another process's numa_maps would silently produce plausible wrong numbers.
        try:
            comm = open(f"/proc/{p.pid}/comm").read().strip()
        except OSError:
            comm = "?"
        if comm != "llama-server":
            raise Abort(f"{label}: pid {p.pid} is {comm!r}, not llama-server -- placement would be wrong")
        place = numa_placement(p.pid)
        emit({"stage": "load", "ok": True, "load_s": round(time.time() - t0, 1), **base,
              "gpu_after_load": gpu_mib(), "cmd": cmd, "pre": list(pre or []), "comm": comm,
              "placement_after_load": place, "numastat_after_load": numastat(p.pid),
              # Functional evidence, not a log string: -lm dio is accepted by builds that do not document
              # it, so "the flag parsed" proves nothing. The scorer gates on load_s against the mmap arm.
              "dio_requested": "dio" in flags,
              "dio_log_hits": len(re.findall(r"(?i)direct\s*-?\s*io", text))})
        log(f"{label}: placement after load {place.get('total_mib')} imbalance {place.get('imbalance')}")

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
        # Placement is re-read after the timed requests: pages move as they are touched, and the figure
        # that matters for decode is the one that held while decode was running, not at load.
        emit({"stage": "arm_done", "arm": label, "peak_mib": peak.peak, "wall_s": round(time.time() - t0, 1),
              "placement_after_run": numa_placement(p.pid), "numastat_after_run": numastat(p.pid)})
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
    stage = ("db" if "--dimm-before" in sys.argv else "da" if "--dimm-after" in sys.argv
             else "5a" if "--stage5a" in sys.argv else "5b" if "--stage5b" in sys.argv
             else "5c" if "--stage5c" in sys.argv
             else "5d" if "--stage5d" in sys.argv
             else "3b" if "--stage3b" in sys.argv else 4 if "--stage4" in sys.argv
             else 3 if "--stage3" in sys.argv else 2 if "--stage2" in sys.argv else 1)
    try:
        # The dimm stages require a specific clock; every other stage records whatever it finds.
        ver, clk = gates(require_clock=DIMM_CLOCK if stage in ("db", "da") else None)
        emit({"stage": "gates", "ok": True, "version": ver[:300], "clocks": clk, "run_stage": stage,
              "driver_sha": DRIVER_SHA})
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
        elif stage == "5a":
            queue = list(STAGE5A)
        elif stage == "5b":
            queue = list(STAGE5B)
        elif stage == "5c":
            queue = list(STAGE5C)
        elif stage == "5d":
            queue = list(STAGE5D)
        elif stage == "db":
            queue = list(DIMM_BEFORE)
        elif stage == "da":
            queue = list(DIMM_AFTER)
        else:
            bandwidth()
            queue = list(ARMS)
        done = {r["arm"] for r in rows() if r.get("stage") == "arm_done"}
        while queue:
            item = queue.pop(0)
            label, stem, flags = item[0], item[1], item[2]
            pre = item[3] if len(item) > 3 else None   # Stage 5c arms carry an external numactl prefix
            if label in done:
                log(f"{label} already complete -- skipping")
                continue
            loaded = run_arm(label, stem, flags, pre)
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
