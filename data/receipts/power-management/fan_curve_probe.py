#!/usr/bin/env python3
"""What does .73's blower curve follow? The two P100 blowers hang off a motherboard fan header (BIOS curve) through a
MOSFET and an external 24 V supply; Linux exposes no fan PWM or RPM on this board (no Super I/O driver binds).
So the curve is inferred from the cards themselves: hold GPU load constant, add CPU load on cores the server does not
use, and see whether the GPUs get COOLER at the same GPU power.

Phases (GPU load = ONE generation stream through the wake proxy; CPU load = `yes` on cpus 2-5,8-11).
The first attempt used 3 parallel streams and every request failed with HTTP 500: the daily driver's CUDA pool ran out
of VRAM on a 3-sequence batch (see NOTE_FAN_CURVE_73.md). One stream is what the box can serve.
  idle 90 s | GPU 6 min | GPU+CPU 6 min | GPU 5 min | CPU only 3 min | idle 60 s
Sampler on .73 every 2 s: GPU temp/power/util per card, CPU package temp. Aborts the load if a card reaches 78 C
(slowdown is 82 C, shutdown 85 C). Output: fan_curve/samples.csv, fan_curve/phases.json.
"""
import json, signal, subprocess, sys, threading, time, urllib.request
from pathlib import Path

H = "10.0.0.73"; PROXY = "http://127.0.0.1:8099"
OUT = Path(__file__).resolve().parent / "fan_curve"; OUT.mkdir(exist_ok=True)
PHASES = [("idle0", 90, 0, 0), ("gpu1", 360, 1, 0), ("gpu+cpu", 360, 1, 1), ("gpu2", 300, 1, 0), ("cpu", 180, 0, 1), ("idle1", 60, 0, 0)]
LIMIT = 78
stop_gen = threading.Event()


def ssh(cmd, timeout=60):
    return subprocess.run(["ssh", "-n", "-o", "BatchMode=yes", H, cmd], capture_output=True, text=True, timeout=timeout).stdout.strip()


def gen_loop():
    body = json.dumps({"messages": [{"role": "user", "content": "Write a very long, detailed history of lighthouses, era by era."}],
                       "max_tokens": 3000, "temperature": 0.7, "cache_prompt": False,
                       "chat_template_kwargs": {"enable_thinking": False}}).encode()
    while not stop_gen.is_set():
        try:
            urllib.request.urlopen(urllib.request.Request(PROXY + "/v1/chat/completions", body, {"content-type": "application/json"}), timeout=900).read()
        except Exception as e:                                   # noqa: BLE001
            print("gen error:", e, flush=True); time.sleep(5)


def max_temp():
    t = ssh("timeout 5 nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits")
    return max(int(x) for x in t.split()) if t else 0


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))   # so `finally` cleans up
    sampler = ssh("nohup sh -c 'while true; do echo \"$(date +%s),$(timeout 5 nvidia-smi --query-gpu=temperature.gpu,power.draw,utilization.gpu "
                  "--format=csv,noheader,nounits | tr \"\\n\" \",\" | tr -d \" \")$(cat /sys/class/hwmon/hwmon3/temp1_input)\"; sleep 2; done' "
                  "> ~/fan_curve_samples.csv 2>/dev/null < /dev/null & echo $!")
    print("sampler pid", sampler, flush=True)
    marks, threads, cpu_on, aborted = [], [], False, False
    try:
        for name, secs, gpu, cpu in PHASES:
            if gpu and not threads and not aborted:
                stop_gen.clear(); threads = [threading.Thread(target=gen_loop, daemon=True) for _ in range(1)]
                [t.start() for t in threads]
            if not gpu and threads:
                stop_gen.set(); threads = []                     # in-flight requests finish on their own (<= ~2 min)
            if cpu and not cpu_on:
                ssh(f"for i in 1 2 3 4 5 6 7 8; do nohup taskset -c 2-5,8-11 timeout {secs + 5} yes > /dev/null 2>&1 < /dev/null & done"); cpu_on = True
            if not cpu and cpu_on:
                ssh("pkill -x yes"); cpu_on = False
            t0 = int(ssh("date +%s")); marks.append({"phase": name, "t0": t0, "secs": secs, "gpu": gpu, "cpu": cpu})
            print(f"{time.strftime('%T')} phase {name} ({secs}s)", flush=True)
            end = time.time() + secs
            while time.time() < end:
                time.sleep(15)
                mt = max_temp()
                if mt >= LIMIT and not aborted:
                    print(f"ABORT load: GPU at {mt} C", flush=True); stop_gen.set(); threads = []; aborted = True
                    marks.append({"phase": "ABORT", "t0": int(ssh("date +%s")), "temp": mt})
    finally:
        stop_gen.set(); ssh("pkill -x yes")
        if ssh(f"cat /proc/{sampler}/comm") == "sh":
            ssh(f"pkill -P {sampler}; kill {sampler}")
        subprocess.run(["scp", "-q", f"{H}:fan_curve_samples.csv", str(OUT / "samples.csv")])
        json.dump(marks, open(OUT / "phases.json", "w"), indent=1)
        print("done", flush=True)


if __name__ == "__main__":
    main()
