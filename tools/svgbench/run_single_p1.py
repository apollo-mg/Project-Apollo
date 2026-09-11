#!/usr/bin/env python3
"""First drawings only, for one model, with run_ladder.py's settings and memory safeguards unchanged.

Used for data/receipts/svgbench-davidau/PREREG_TOKENS.md. Only the model, the label and the output
directory differ from the ladder. The server flags, prompt, sampling, scorer and safeguards are
run_ladder's own functions, called as-is.

Usage: run_single_p1.py MODEL.gguf LABEL OUT_DIR [REPS]
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_ladder as R  # noqa: E402


def main():
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    model, label, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    reps = int(sys.argv[4]) if len(sys.argv) == 5 else R.REPS
    R.OUT = out                      # record(), records() and base() read OUT at call time
    out.mkdir(parents=True, exist_ok=True)
    for rep in range(1, reps + 1):
        if R.last(label, rep, "p1") is not None:
            continue                 # resume: this rep's first drawing is already recorded
        if not R.wait_for_memory(f"{label} rep {rep}"):
            R.record({"quant": label, "rep": rep, "step": "server",
                      "error": f"skipped: MemAvailable never reached {R.MEM_START_GB} GB", "ts": time.time()})
            continue
        print(f"{time.strftime('%H:%M:%S')} === {label} rep {rep} ===", flush=True)
        p, ok = R.start_server(model, out / f"server_{label}_r{rep}.log")
        if not ok:
            R.record({"quant": label, "rep": rep, "step": "server", "error": "server never ready",
                      "ts": time.time()})
            R.stop_server(p)
            R.cooldown()
            continue
        wd = R.MemWatchdog(p)
        wd.start()
        try:
            R.do_step(label, rep, "p1", R.TASK, None)
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
              f"finish {r.get('finish')}", flush=True)
    print(f"{time.strftime('%H:%M:%S')} === DONE ===", flush=True)


if __name__ == "__main__":
    main()
