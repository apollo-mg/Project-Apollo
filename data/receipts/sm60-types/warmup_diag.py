#!/usr/bin/env python3
"""NOTE_WARMUP_DIAGNOSIS.md: per-request decode tok/s and llama-server major-fault delta. usage: warmup_diag.py URL PID LABEL SET OUT
SET = fixed (the 6 speed prompts) | novel (6 prompts not in the set)"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qwen4exp"))
from run_mtp_clock import PROMPTS  # noqa: E402
NOVEL = [("n1", "Describe the life cycle of a monarch butterfly in detail."),
         ("n2", "Write a Rust function that merges two sorted vectors, with unit tests."),
         ("n3", "Explain why the sky appears red at sunset, covering Rayleigh scattering."),
         ("n4", "Summarise the causes and consequences of the 1929 stock market crash."),
         ("n5", "Give 20 ideas for a rainy-day science activity with household items."),
         ("n6", "Translate into French and explain the grammar: 'We would have left earlier if it had not rained.'")]
url, pid, label, which, out = sys.argv[1:6]
def majflt():
    return int(subprocess.run(["ssh", "10.0.0.194", f"cut -d' ' -f12 /proc/{pid}/stat"], capture_output=True, text=True).stdout.strip())
with open(out, "a") as f:
    for name, p in (PROMPTS if which == "fixed" else NOVEL):
        m0 = majflt()
        body = {"messages": [{"role": "user", "content": p}], "max_tokens": 384, "temperature": 0, "seed": 1,
                "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False}}
        r = json.load(urllib.request.urlopen(urllib.request.Request(url + "/v1/chat/completions", json.dumps(body).encode(),
                                                                    {"content-type": "application/json"}), timeout=900))
        m1 = majflt(); tm = r.get("timings") or {}
        row = {"label": label, "prompt": name, "tps": tm.get("predicted_per_second"), "n": tm.get("predicted_n"), "majflt": m1 - m0}
        f.write(json.dumps(row) + "\n"); f.flush(); os.fsync(f.fileno())
        print(f"{label:10s} {name:8s} {row['tps']:6.2f} tok/s  majflt +{row['majflt']}", flush=True)
