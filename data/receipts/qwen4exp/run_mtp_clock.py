#!/usr/bin/env python3
"""PREREG_FLASHNEXT_MTP_CLOCK.md: Flash-Next UD-Q2_K_XL fully resident on .194 (4x P100, -ngl 99, layer split),
MTP off/on x three GPU configs, with power logged for tok/J.

  E  -pl 150 -ac 715,1063   the fleet efficiency service (p100-efficiency.service)
  P  -pl 150 -ac 715,1328   the clock alone raised
  B  -pl 250 -rac           boot default (cap raised, autoboost)

Per MTP setting: one fresh VERIFIED server (AFM-50: stopped by name; own log loaded; /props file; offload 49/49; MTP
engaged when on), one discarded warm-up, then blocks E P B B P E. Each block runs 6 fixed prompts (temp 0, thinking
off, 384 tokens, cache_prompt false) and one cold ~6k-token prefill (max_tokens 1). One nvidia-smi sampler at 200 ms
(its own PID, checked by comm before kill) logs every GPU. Request windows are aligned by a measured clock offset.
The efficiency config is ALWAYS restored on exit (systemctl restart p100-efficiency, read back).
Rows: mtp_clock/rows.jsonl (flush+fsync), power: mtp_clock/power.csv.
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "mtp_clock"; OUT.mkdir(exist_ok=True)
H, PORT = "10.0.0.194", 8190
URL = f"http://{H}:{PORT}"
BIN = "~/buun-0b278/build_sm60/bin/llama-server"
Q2 = "~/AI/Models/flashnext_q2/Qwen3.8-Flash-Next-UD-Q2_K_XL-00001-of-00003.gguf"
MTP = "-md ~/AI/Models/flashnext_mtp/mtp-Qwen3.8-Flash-Next-shared-Q8_0.gguf --spec-type draft-mtp --spec-draft-n-max 3"
FLAGS = f"-ngl 99 -sm layer -ts 1,1,1,0.6 -c 8192 -ctk f16 -ctv f16 -np 1 -fit off -lv 4 --host 0.0.0.0 --port {PORT}"
CFG = {"E": "sudo nvidia-smi -pl 150 >/dev/null && sudo nvidia-smi -ac 715,1063 >/dev/null",
       "P": "sudo nvidia-smi -pl 150 >/dev/null && sudo nvidia-smi -ac 715,1328 >/dev/null",
       "B": "sudo nvidia-smi -pl 250 >/dev/null && sudo nvidia-smi -rac >/dev/null"}
ORDER = ["E", "P", "B", "B", "P", "E"]
PROMPTS = [
    ("prose", "Write a 300-word short story about a lighthouse keeper who finds a message in a bottle."),
    ("explain", "Explain how a refrigerator moves heat out of its interior, step by step, for a curious teenager."),
    ("code", "Write a Python function that parses an ISO-8601 date string without using datetime.fromisoformat, with docstring and tests."),
    ("json", "Extract every person, place and date from this text as JSON with keys people, places, dates: "
             "'On 3 March 1921, Marie Curie travelled from Paris to New York, where she met Warren Harding on 20 May.'"),
    ("math", "A tank fills at 12 litres per minute and drains at 5 litres per minute. It starts with 40 litres. "
             "How long until it holds 250 litres? Show the working."),
    ("list", "List 25 practical tips for keeping a home workshop organised, one line each."),
]
LOG = OUT / "run.log"


def log(m):
    line = f"{time.strftime('%F %T')} {m}"; print(line, flush=True); open(LOG, "a").write(line + "\n")


def ssh(cmd, check=True, timeout=120):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", H, cmd], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f"ssh failed ({r.returncode}): {cmd[:80]} :: {r.stderr[:200]}")
    return r.stdout.strip()


def http(path, body=None, timeout=900):
    req = urllib.request.Request(URL + path, json.dumps(body).encode() if body is not None else None,
                                 {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def stop_server():
    ssh("pkill -x llama-server; for i in $(seq 1 60); do pgrep -x llama-server >/dev/null || exit 0; sleep 1; done; exit 1")


def start_server(tag, mtp):
    stop_server()
    ssh(f"CUDA_VISIBLE_DEVICES=0,1,2,3 GGML_CUDA_ALLREDUCE=internal nohup {BIN} -m {Q2} {FLAGS} {MTP if mtp else ''} "
        f"> ~/mtpclk_{tag}.log 2>&1 < /dev/null &")
    for _ in range(120):
        time.sleep(5)
        if ssh("pgrep -x llama-server >/dev/null && echo up || echo down", check=False) != "up":
            raise RuntimeError(f"{tag}: server died: {ssh(f'tail -3 ~/mtpclk_{tag}.log', check=False)}")
        if ssh(f"grep -q 'model loaded' ~/mtpclk_{tag}.log && echo y || echo n", check=False) == "y":
            try:
                http("/health", timeout=5); break
            except Exception:
                pass
    else:
        raise RuntimeError(f"{tag}: not healthy")
    mp = http("/props").get("model_path", "")
    assert mp.endswith(Q2.split("/")[-1]), f"{tag}: WRONG SERVER {mp}"
    assert ssh(f"grep -c 'offloaded 49/49 layers to GPU' ~/mtpclk_{tag}.log", check=False) != "0", f"{tag}: placement"
    return mp


def set_cfg(c):
    ssh(CFG[c]); time.sleep(10)
    return ssh("nvidia-smi --query-gpu=power.limit,clocks.applications.graphics --format=csv,noheader | sort -u | tr '\\n' ';'")


def restore():
    try:
        ssh("sudo systemctl restart p100-efficiency")
        log("restored efficiency config: " + ssh("nvidia-smi --query-gpu=power.limit,clocks.applications.graphics "
                                                 "--format=csv,noheader | sort -u | tr '\\n' ';'"))
    except Exception as e:                                                   # noqa: BLE001
        log(f"RESTORE FAILED: {e} -- run: ssh {H} sudo systemctl restart p100-efficiency")


def main():
    long_text = (HERE.parent / "quant-abstention" / "RESULT_MAIN.md").read_text()[:24000]   # fixed ~6k-token prefill
    rows_p = OUT / "rows.jsonl"
    sampler = None
    try:
        # clock offset: remote - local, from the midpoint of an ssh round trip
        t0 = time.time(); rt = float(ssh("date +%s.%N")); t1 = time.time(); off = rt - (t0 + t1) / 2
        log(f"clock offset remote-local {off:+.3f} s (rtt {t1 - t0:.3f})")
        sampler = ssh("bash -c 'nohup nvidia-smi --query-gpu=timestamp,index,power.draw,clocks.sm --format=csv,noheader,nounits "
                      "-lms 200 > ~/mtpclk_power.csv 2>&1 < /dev/null & echo $!'")
        assert ssh(f"cat /proc/{sampler}/comm", check=False) == "nvidia-smi", "sampler PID is not nvidia-smi"
        with open(rows_p, "a") as f:
            for mtp in (False, True):
                tag = "on" if mtp else "off"
                start_server(tag, mtp)
                if mtp:
                    w = http("/v1/chat/completions", {"messages": [{"role": "user", "content": "Count from 1 to 20."}],
                             "max_tokens": 64, "temperature": 0, "cache_prompt": False,
                             "chat_template_kwargs": {"enable_thinking": False}})
                    assert (w.get("timings") or {}).get("draft_n", 0) > 0, "MTP did not engage"
                else:
                    http("/v1/chat/completions", {"messages": [{"role": "user", "content": "Say ready."}], "max_tokens": 8,
                         "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}})
                log(f"MTP {tag}: server verified, warm-up discarded")
                for blk, c in enumerate(ORDER):
                    live = set_cfg(c)
                    log(f"MTP {tag} block {blk} cfg {c}: {live}")
                    jobs = [(pid, p, 384) for pid, p in PROMPTS] + [("prefill", "Summarise in one word:\n\n" + long_text, 1)]
                    for pid, p, n in jobs:
                        ts = time.time() + off
                        r = http("/v1/chat/completions", {"messages": [{"role": "user", "content": p}], "max_tokens": n,
                                 "temperature": 0, "seed": 1, "cache_prompt": False,
                                 "chat_template_kwargs": {"enable_thinking": False}})
                        te = time.time() + off
                        tm = r.get("timings") or {}
                        row = {"mtp": tag, "cfg": c, "block": blk, "prompt": pid, "t0": ts, "t1": te, "live": live,
                               "predicted_n": tm.get("predicted_n"), "predicted_per_second": tm.get("predicted_per_second"),
                               "predicted_ms": tm.get("predicted_ms"), "prompt_n": tm.get("prompt_n"),
                               "prompt_per_second": tm.get("prompt_per_second"), "prompt_ms": tm.get("prompt_ms"),
                               "draft_n": tm.get("draft_n"), "draft_n_accepted": tm.get("draft_n_accepted")}
                        f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
                        log(f"  {tag} {c} {pid:8s} dec {row['predicted_per_second'] or 0:6.2f} tok/s  pre {row['prompt_per_second'] or 0:7.1f}"
                            + (f"  acc {row['draft_n_accepted']}/{row['draft_n']}" if row.get("draft_n") else ""))
        log("ALL_DONE")
    finally:
        try:
            stop_server()
        except Exception:                                                   # noqa: BLE001
            pass
        if sampler and ssh(f"cat /proc/{sampler}/comm", check=False) == "nvidia-smi":
            ssh(f"kill {sampler}", check=False)
        subprocess.run(["scp", "-q", f"{H}:mtpclk_power.csv", str(OUT / "power.csv")])
        restore()


if __name__ == "__main__":
    main()
