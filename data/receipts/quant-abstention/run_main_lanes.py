#!/usr/bin/env python3
"""Drive the main campaign on .194's two lanes (PREREG_MAIN.md). Runs on the desktop; resumable.

Order:
1. The bridge. Q8_0 runs on both lanes at once (C.A, C.B) over all 240 items. The bridge check (analyze_main.bridge)
   decides whether lane B may continue. On a fail, every other arm runs on lane A.
2. The queue: every non-ceiling arm in arms_main.json, EXL3 last. Each arm is:
   - staged from the desktop registry file to ~/qa_stage/<lane>/;
   - sha256-verified against arms_main.json (files: sha256; EXL3 dirs: the sha256 of the per-file manifest);
   - served (serve_main.sh), run (run_main.py), logged, then its staged copy is deleted.
3. The first EXL3 arm must show the f16 KV line and no MTP/draft line in its log; otherwise the remaining EXL3 arms
   are held (PREREG_MAIN: EXL3 verification).

State lives in raw/main_lanes_state.json: the lane each arm ran on (an arm resumes on its own lane), bridge result,
holds. A run is complete when raw/main_<arm>.jsonl has a header plus one row per M1 item.
"""
import hashlib, json, os, queue, re, shlex, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = "10.0.0.194"
ROOT = "/mnt/TG_2TB/AI/Models"
PY = str(HERE.parents[2] / "venv_cachyos" / "bin" / "python3")
PORT = {"A": 8190, "B": 8191}
C_ON_194 = "~/AI/Models/ladder_ud/Qwen3.8-27B-Q8_0.gguf"      # the ceiling is already on .194, hash-verified
N_ITEMS = sum(1 for _ in open(HERE / "corpus" / "M1.jsonl"))
REG = {a["arm"]: a for a in json.load(open(HERE / "arms_main.json"))["arms"]}
STATE_P = HERE / "raw" / "main_lanes_state.json"
LOG_P = HERE / "raw" / "main_lanes.log"
lock = threading.Lock()


def log(msg):
    line = time.strftime("%F %T ") + msg
    with lock, open(LOG_P, "a") as f:
        f.write(line + "\n"); f.flush(); os.fsync(f.fileno())
    print(line, flush=True)


def state():
    return json.load(open(STATE_P)) if STATE_P.exists() else {"lane_of": {}, "bridge": None, "holds": []}


def save(st):
    with lock:
        tmp = STATE_P.with_suffix(".tmp"); json.dump(st, open(tmp, "w"), indent=1); os.replace(tmp, STATE_P)


def ssh(cmd, check=True):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", H, cmd], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise RuntimeError(f"ssh failed ({r.returncode}): {cmd[:120]} :: {r.stdout[-400:]} {r.stderr[-400:]}")
    return r.stdout


def done(name):
    p = HERE / "raw" / f"main_{name}.jsonl"
    return p.exists() and sum(1 for _ in open(p)) >= N_ITEMS + 1


def free_gb():
    return int(ssh("df --output=avail -B1G ~ | tail -n 1").strip())


def stage(lane, arm):
    a = REG[arm]
    src = os.path.join(ROOT, a["path"])
    is_dir = os.path.isdir(src)
    size_gb = (sum(os.path.getsize(os.path.join(src, f)) for f in os.listdir(src)) if is_dir else os.path.getsize(src)) / 2**30
    need = size_gb * (2 if is_dir else 1) + 10          # EXL3 import stages a second copy in LLAMA_CACHE
    for _ in range(60):
        if free_gb() >= need:
            break
        log(f"[{lane}] {arm}: waiting for disk ({need:.0f} GB needed)"); time.sleep(30)
    else:
        raise RuntimeError(f"{arm}: not enough disk on .194")
    dst = f"qa_stage/{lane}/" + os.path.basename(src.rstrip("/"))
    ssh(f"mkdir -p ~/qa_stage/{lane}")
    r = subprocess.run(["rsync", "-a", src.rstrip("/") + ("/" if is_dir else ""), f"{H}:{dst}" + ("/" if is_dir else "")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"rsync {arm}: {r.stderr[-300:]}")
    if is_dir:
        man = json.loads(ssh("cd ~/" + shlex.quote(dst) + " && python3 -c 'import hashlib,json,os\n"
                             "m={}\nfor f in sorted(os.listdir(\".\")):\n"
                             "  if f.startswith(\".\") or not os.path.isfile(f): continue\n"
                             "  h=hashlib.sha256()\n  fh=open(f,\"rb\")\n"
                             "  for c in iter(lambda: fh.read(1<<24), b\"\"): h.update(c)\n"
                             "  m[f]=h.hexdigest()\nprint(json.dumps(m))'"))
        got = hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest()
    else:
        got = ssh(f"sha256sum ~/{shlex.quote(dst)}").split()[0]
    if got != a["sha256"]:
        raise RuntimeError(f"{arm}: sha256 mismatch after staging ({got[:12]} != {a['sha256'][:12]})")
    return "~/" + dst, got


def run_arm(lane, name, model, sha):
    try:
        return _run_arm(lane, name, model, sha)
    except Exception as e:                      # noqa: BLE001  (logged here so thread failures are never silent)
        log(f"[{lane}] {name}: ERROR {e}")
        raise


def _run_arm(lane, name, model, sha):
    log(f"[{lane}] {name}: serving {model}")
    ssh(f"bash ~/qa_serve_main.sh {lane} {shlex.quote(name)} {model} {sha}")
    meta = json.loads(ssh(f"cat ~/qa_main_meta_{name}.json"))
    (HERE / "raw" / "logs").mkdir(parents=True, exist_ok=True)
    json.dump(meta, open(HERE / "raw" / "logs" / f"main_meta_{name}.json", "w"), indent=1)
    if not meta["kv_f16_verified"]:
        raise RuntimeError(f"{name}: f16 KV line not found in the server log")
    log(f"[{lane}] {name}: running items")
    r = subprocess.run([PY, str(HERE / "run_main.py"), "--url", f"http://{H}:{PORT[lane]}", "--arm", name,
                        "--meta", json.dumps(meta), "--corpus", "M1", "--max-tokens", "1024"],
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0 or not done(name):
        raise RuntimeError(f"{name}: runner failed: {r.stderr[-600:]}")
    logp = HERE / "raw" / "logs" / f"main_server_{name}.log"
    subprocess.run(["scp", "-q", f"{H}:qa_main_server_{name}.log", str(logp)], check=True)
    txt = re.sub(r"/home/[a-z]+", "~", open(logp, errors="replace").read())
    open(logp, "w").write(txt)
    subprocess.run(["gzip", "-9f", str(logp)], check=True)
    log(f"[{lane}] {name}: done")
    return meta


def worker(lane, q, st):
    while True:
        try:
            arm = q.get_nowait()
        except queue.Empty:
            return
        if done(arm):
            continue
        if st["lane_of"].setdefault(arm, lane) != lane:
            q.put(arm); time.sleep(5)          # an interrupted arm resumes on its own lane
            if all(st["lane_of"].get(x) not in (None, lane) for x in list(q.queue)):
                return
            continue
        save(st)
        if REG[arm]["family"] == "EXL3" and "EXL3" in st["holds"]:
            log(f"[{lane}] {arm}: HELD (first EXL3 arm failed verification)"); continue
        try:
            model, sha = stage(lane, arm)
            meta = run_arm(lane, arm, model, sha)
            if REG[arm]["family"] == "EXL3" and meta.get("mtp_or_draft_line_seen"):
                st["holds"].append("EXL3"); save(st)
                log(f"[{lane}] {arm}: an MTP/draft line was seen in the EXL3 log: holding the other EXL3 arms")
        except Exception as e:                  # noqa: BLE001
            log(f"[{lane}] {arm}: ERROR {e}")
        finally:
            ssh(f"rm -rf ~/qa_stage/{lane}/* ~/qa_stage/cache_{lane}/*", check=False)


def main():
    subprocess.run(["scp", "-q", str(HERE / "serve_main.sh"), f"{H}:qa_serve_main.sh"], check=True)
    st = state()
    # 1. bridge
    if st["bridge"] is None:
        c_sha = REG["C"]["sha256"]
        ts = [threading.Thread(target=lambda ln: None if done(f"C.{ln}") else run_arm(ln, f"C.{ln}", C_ON_194, c_sha),
                               args=(ln,)) for ln in "AB"]
        [t.start() for t in ts]; [t.join() for t in ts]
        if not (done("C.A") and done("C.B")):
            log("BRIDGE: a ceiling run is incomplete; stopping (see the lane errors above)")
            sys.exit(1)
        sys.path.insert(0, str(HERE))
        from analyze_main import bridge
        st["bridge"] = bridge(HERE / "raw" / "main_C.A.jsonl", HERE / "raw" / "main_C.B.jsonl")
        save(st)
        log(f"BRIDGE: {st['bridge']}")
    lanes = "AB" if st["bridge"].get("pass") else "A"
    # 2. queue
    order = sorted((a for a in REG if a != "C"), key=lambda a: (REG[a]["family"] == "EXL3", REG[a]["scored_bpw"] or 0))
    q = queue.Queue()
    for a in order:
        q.put(a)
    ts = [threading.Thread(target=worker, args=(ln, q, st)) for ln in lanes]
    [t.start() for t in ts]; [t.join() for t in ts]
    for ln in "AB":
        ssh(f"f=~/qa_main_server_{ln}.pid; [ -f $f ] && kill $(cat $f) 2>/dev/null; true", check=False)
    missing = [a for a in REG if a != "C" and not done(a)]
    log(f"ALL LANES DONE; incomplete arms: {missing}")


if __name__ == "__main__":
    main()
