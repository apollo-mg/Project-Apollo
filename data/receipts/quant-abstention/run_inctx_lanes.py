#!/usr/bin/env python3
"""Drive the in-context slot readout (PREREG_INCTX.md) on .194's two lanes. Runs on the desktop; resumable.

- Lane B: Q8_0 (already on .194) reads its own prose (all items), then the prose of the 7 key files (U items only).
  Then it joins the shared queue.
- Lane A: the EXL3 arms first (EXL3 only ever runs on lane A: disk staging, as in main), then the shared queue.
- Shared queue: the key files first, then the rest by scored bpw. Each arm is:
  - staged and sha256-verified (run_main_lanes.stage);
  - served with the main flags (serve_main.sh), with the f16 KV line and no MTP/draft line required;
  - read: its own prose (all items), plus Q8_0's prose (U items) for a key file;
  - its staged copy deleted.
A pass is complete when its output has a header plus one row per usable item.
"""
import json, queue, subprocess, sys, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_main_lanes as rml  # noqa: E402

rml.LOG_P = HERE / "raw" / "inctx_lanes.log"
PY, H, PORT = rml.PY, rml.H, rml.PORT
KEY = ["AD2XS", "AP3XXS", "APEXN", "EXL30", "EXL35", "AD3XXS", "BON1"]
ITEMS = {x["id"]: x for x in map(json.loads, open(HERE / "corpus" / "M1.jsonl"))}


def usable(writer, item_arms):
    src = HERE / "raw" / ("main_C.A.jsonl" if writer == "C" else f"main_{writer}.jsonl")
    rows = list(map(json.loads, list(open(src))[1:]))
    return sum(1 for r in rows if "Exact Answer:" in r["content"] and ITEMS[r["id"]]["arm"] in item_arms)


def done(reader, writer, item_arms):
    p = HERE / "raw" / f"inctx_{reader}__{writer}.jsonl"
    return p.exists() and sum(1 for _ in open(p)) >= usable(writer, item_arms) + 1


def serve(lane, name, model, sha):
    rml.log(f"[{lane}] {name}: serving {model}")
    rml.ssh(f"bash ~/qa_serve_main.sh {lane} INCTX_{name} {model} {sha}")
    meta = json.loads(rml.ssh(f"cat ~/qa_main_meta_INCTX_{name}.json"))
    (HERE / "raw" / "logs").mkdir(parents=True, exist_ok=True)
    json.dump(meta, open(HERE / "raw" / "logs" / f"inctx_meta_{name}.json", "w"), indent=1)
    if not meta["kv_f16_verified"] or meta.get("mtp_or_draft_line_seen"):
        raise RuntimeError(f"{name}: KV/MTP verification failed")
    return meta


def read(lane, reader, writer, item_arms, meta):
    if done(reader, writer, item_arms):
        return
    rml.log(f"[{lane}] {reader} reads {writer} ({item_arms})")
    r = subprocess.run([PY, str(HERE / "run_inctx.py"), "--url", f"http://{H}:{PORT[lane]}", "--reader", reader,
                        "--writers", writer, "--item-arms", item_arms, "--meta", json.dumps(meta)],
                       capture_output=True, text=True, cwd=HERE, timeout=2 * 3600)
    probe = [l for l in r.stdout.splitlines() if l.startswith("PROBE")]
    if r.returncode != 0 or not done(reader, writer, item_arms):
        raise RuntimeError(f"{reader}<-{writer}: runner failed: {r.stderr[-600:]}")
    rml.log(f"[{lane}] {reader} reads {writer}: done {probe}")


def arm_job(lane, arm):
    need_swap = arm in KEY
    if done(arm, arm, "EHU") and (not need_swap or done(arm, "C", "U")):
        return
    try:
        model, sha = rml.stage(lane, arm)
        meta = serve(lane, arm, model, sha)
        read(lane, arm, arm, "EHU", meta)
        if need_swap:
            read(lane, arm, "C", "U", meta)
        subprocess.run(["scp", "-q", f"{H}:qa_main_server_INCTX_{arm}.log", str(HERE / "raw" / "logs" / f"inctx_server_{arm}.log")])
    except Exception as e:                      # noqa: BLE001
        rml.log(f"[{lane}] {arm}: ERROR {e}")
    finally:
        rml.ssh(f"rm -rf ~/qa_stage/{lane}/* ~/qa_stage/cache_{lane}/*", check=False)


def lane_worker(lane, first, q):
    for arm in first:
        arm_job(lane, arm)
    while True:
        try:
            arm = q.get_nowait()
        except queue.Empty:
            return
        arm_job(lane, arm)


def ceiling_then_queue(q):
    try:
        meta = serve("B", "C", rml.C_ON_194, rml.REG["C"]["sha256"])
        read("B", "C", "C", "EHU", meta)
        for w in KEY:
            read("B", "C", w, "U", meta)
        subprocess.run(["scp", "-q", f"{H}:qa_main_server_INCTX_C.log", str(HERE / "raw" / "logs" / "inctx_server_C.log")])
    except Exception as e:                      # noqa: BLE001
        rml.log(f"[B] C: ERROR {e}")
        return                                  # without the ceiling passes, lane B takes no arms (instrument check)
    lane_worker("B", [], q)


def main():
    rml.subprocess.run(["scp", "-q", str(HERE / "serve_main.sh"), f"{H}:qa_serve_main.sh"], check=True)
    exl = [a for a in rml.REG if rml.REG[a]["family"] == "EXL3"]
    exl.sort(key=lambda a: (a not in KEY, rml.REG[a]["scored_bpw"]))
    rest = [a for a in rml.REG if a != "C" and a not in exl]
    rest.sort(key=lambda a: (a not in KEY, rml.REG[a]["scored_bpw"] or 0))
    q = queue.Queue()
    for a in rest:
        q.put(a)
    ts = [threading.Thread(target=lane_worker, args=("A", exl, q)), threading.Thread(target=ceiling_then_queue, args=(q,))]
    [t.start() for t in ts]; [t.join() for t in ts]
    for ln in "AB":
        rml.ssh(f"f=~/qa_main_server_{ln}.pid; [ -f $f ] && kill $(cat $f) 2>/dev/null; true", check=False)
    missing = [a for a in rml.REG if a != "C" and not done(a, a, "EHU")]
    rml.log(f"ALL LANES DONE; arms without an own-prose pass: {missing}")


if __name__ == "__main__":
    main()
