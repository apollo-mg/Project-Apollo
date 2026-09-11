#!/usr/bin/env python3
"""One first drawing for one arm, with run_ladder.py's settings and memory safeguards unchanged.

Used for data/receipts/svgbench-pelican3/PREREG_PELICAN3.md. Differences from run_single_p1.py:
- **One rep per call,** so each call fits a 10-minute foreground job.
- **Capped generation.** Generation is capped at GEN_CAP_S seconds (the HTTP read timeout). A capped
  rep is recorded, not rerun: rule R1.
- **Meta record.** Once the server is ready, a "meta" record stores the prompt the server itself
  renders (/apply-template) and the live KV bits per value (/slots kv_bpv): rules R4 and R5.

Usage: run_one_p1.py MODEL.gguf LABEL OUT_DIR REP
"""
import hashlib, json, sys, time, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_ladder as R  # noqa: E402

GEN_CAP_S = 480

_post = R.post


def post_capped(body, timeout=GEN_CAP_S):
    return _post(body, min(timeout, GEN_CAP_S))


R.post = post_capped   # generate() calls post(body) and gets the cap; start_server's 10 s probe keeps its 10 s


def get_json(path, body=None, timeout=15):
    req = urllib.request.Request(f"http://127.0.0.1:8090{path}",
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def meta(label, rep, out):
    rec = {"quant": label, "rep": rep, "step": "meta", "ts": time.time()}
    try:
        prompt = get_json("/apply-template", {"messages": [{"role": "user", "content": R.TASK}]})["prompt"]
        (out / f"prompt_{label}_r{rep}.txt").write_text(prompt)
        rec.update(prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(), prompt_tail=prompt[-24:])
    except Exception as e:
        rec["prompt_error"] = repr(e)[:200]
    try:
        s = get_json("/slots")
        rec["kv_bpv"] = s[0].get("kv_bpv") if isinstance(s, list) and s else None
    except Exception as e:
        rec["slots_error"] = repr(e)[:200]
    R.record(rec)
    return rec


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    model, label, out, rep = sys.argv[1], sys.argv[2], Path(sys.argv[3]), int(sys.argv[4])
    R.OUT = out                      # record(), records() and base() read OUT at call time
    out.mkdir(parents=True, exist_ok=True)
    if R.last(label, rep, "p1") is not None:
        print(f"{label} r{rep} is already recorded; nothing to do", flush=True)
        return
    if not R.wait_for_memory(f"{label} rep {rep}"):
        R.record({"quant": label, "rep": rep, "step": "server",
                  "error": f"skipped: MemAvailable never reached {R.MEM_START_GB} GB", "ts": time.time()})
        return
    print(f"{time.strftime('%H:%M:%S')} === {label} rep {rep} ===", flush=True)
    p, ok = R.start_server(model, out / f"server_{label}_r{rep}.log")
    if not ok:
        R.record({"quant": label, "rep": rep, "step": "server", "error": "server never ready", "ts": time.time()})
        R.stop_server(p)
        R.cooldown()
        return
    wd = R.MemWatchdog(p)
    wd.start()
    generating = False
    try:
        m = meta(label, rep, out)
        print(f"  prompt ends {m.get('prompt_tail')!r} | sha {str(m.get('prompt_sha256'))[:12]} | "
              f"kv_bpv {m.get('kv_bpv')}", flush=True)
        generating = True
        R.do_step(label, rep, "p1", R.TASK, None)
    except KeyboardInterrupt:
        if generating:               # R1: the wall-clock backstop fired mid-generation -- recorded, not rerun
            R.record({"quant": label, "rep": rep, "step": "p1", "ts": time.time(),
                      "error": "wall-clock backstop (SIGINT) during generation"})
        raise
    finally:
        wd.halt.set()
        R.stop_server(p)
        if wd.tripped:
            R.record({"quant": label, "rep": rep, "step": "watchdog", "ts": time.time(),
                      "error": f"memory watchdog SIGKILLed the server: MemAvailable < {R.MEM_FLOOR_GB} GB"})
        R.cooldown()
    r = R.last(label, rep, "p1") or {}
    print(f"{time.strftime('%H:%M:%S')}   {label} r{rep}: tokens {r.get('tokens')}, "
          f"score {r.get('score')}/{r.get('max')}, reasoning chars {r.get('reasoning_chars')}, "
          f"finish {r.get('finish')}, elapsed {r.get('elapsed_s')}s{', ERROR ' + r['error'] if r.get('error') else ''}",
          flush=True)


if __name__ == "__main__":
    main()
