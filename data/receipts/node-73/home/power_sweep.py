#!/usr/bin/env python3
"""Live power-cap sweep on the .73 P100 pair against the resident llama-server.
Sets nvidia-smi -pl per rung, benches prefill+decode via /completion timings,
samples power.draw at 1Hz during each call. Prints a results table."""
import json
import subprocess
import threading
import time
import urllib.request

RUNGS = [250, 230, 210, 190, 170, 150, 125]
PORT = 8082
REPS = 2

PARA = ("The instrument panel of a small aircraft is arranged so that the six primary "
        "flight instruments sit directly in front of the pilot in two rows of three. "
        "The attitude indicator occupies the center of the top row, flanked by the "
        "airspeed indicator on the left and the altimeter on the right, while the "
        "bottom row carries the turn coordinator, heading indicator, and vertical "
        "speed indicator in that order.")


def build_prompt(nonce):
    body = "\n".join(f"Section {i}: {PARA}" for i in range(115))
    return f"RUN-{nonce}\n{body}\nIn one sentence, what do all sections describe?"


def bench(nonce):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/completion",
        data=json.dumps({
            "prompt": build_prompt(nonce), "n_predict": 128,
            "temperature": 0, "cache_prompt": False,
        }).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        return json.load(r)["timings"]


def set_cap(watts):
    subprocess.run(["sudo", "-n", "nvidia-smi", "-pl", str(watts)],
                   check=True, capture_output=True)


def read_draw():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
        capture_output=True, text=True).stdout
    vals = [float(x) for x in out.split() if x.strip()]
    return sum(vals)


samples = []
sampling = threading.Event()


def sampler():
    while True:
        if sampling.is_set():
            try:
                samples.append(read_draw())
            except Exception:  # noqa: BLE001
                pass
        time.sleep(1)


threading.Thread(target=sampler, daemon=True).start()

results = []
nonce = 0
try:
    for w in RUNGS:
        set_cap(w)
        time.sleep(3)
        pp, tg, draws = [], [], []
        for rep in range(REPS):
            nonce += 1
            samples.clear()
            sampling.set()
            t = bench(nonce)
            sampling.clear()
            pp.append(t["prompt_per_second"])
            tg.append(t["predicted_per_second"])
            if samples:
                draws.append(sum(samples) / len(samples))
            print(f"  {w}W rep{rep+1}: pp={t['prompt_per_second']:.1f} "
                  f"tg={t['predicted_per_second']:.2f} "
                  f"draw_mean={draws[-1] if draws else float('nan'):.0f}W "
                  f"draw_max={max(samples) if samples else float('nan'):.0f}W "
                  f"(prompt_n={t['prompt_n']})", flush=True)
        results.append({
            "cap": w,
            "pp": sum(pp) / len(pp), "tg": sum(tg) / len(tg),
            "draw": sum(draws) / len(draws) if draws else None,
        })
finally:
    set_cap(250)
    print("caps restored to 250W", flush=True)

base = results[0]
print(f"\n{'cap':>5} {'prefill t/s':>12} {'%base':>7} {'decode t/s':>11} {'%base':>7} "
      f"{'draw(2gpu)':>11} {'%base':>7}")
for r in results:
    dr = f"{r['draw']:.0f}W" if r["draw"] else "n/a"
    drp = f"{100*r['draw']/base['draw']:.0f}%" if r["draw"] and base["draw"] else "n/a"
    print(f"{r['cap']:>4}W {r['pp']:>12.1f} {100*r['pp']/base['pp']:>6.1f}% "
          f"{r['tg']:>11.2f} {100*r['tg']/base['tg']:>6.1f}% {dr:>11} {drp:>7}")
print("\nDONE_SWEEP")
