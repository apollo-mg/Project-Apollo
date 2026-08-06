#!/usr/bin/env python3
"""Relaunch .73's llama-server from its own captured argv, with MTP spec-decode on or off.

Rebuilding from /proc/<pid>/cmdline (not retyping) guarantees the two arms differ ONLY by
the speculative flags — every other flag, including buun's VBR KV cache settings and the
chat-template-kwargs JSON, is byte-identical.

Usage: relaunch_73.py <on|off>
"""
import os, signal, subprocess, sys, time, urllib.request

MODE   = sys.argv[1]
ARGV_F = "/home/mark/mtp_ab/argv_mtp_on.txt"
LOG    = f"/home/mark/mtp_ab/server_{MODE}.log"
SPEC_FLAGS_WITH_VALUE = {"--spec-type", "--spec-draft-n-max"}

argv = [a for a in open(ARGV_F).read().split("\n") if a != ""]

if MODE == "off":
    out, skip = [], False
    for a in argv:
        if skip:                      skip = False; continue
        if a in SPEC_FLAGS_WITH_VALUE: skip = True;  continue
        out.append(a)
    argv = out
elif MODE != "on":
    sys.exit("mode must be on|off")

# stop whatever is currently serving, by PID (never pkill -f: the pattern matches this process)
try:
    pids = subprocess.check_output(["pgrep", "-f", "buun_vbr/build/bin/llama-server"], text=True).split()
except subprocess.CalledProcessError:
    pids = []
me = str(os.getpid())
for p in pids:
    if p == me: continue
    try:
        os.kill(int(p), signal.SIGTERM); print(f"  SIGTERM {p}")
    except ProcessLookupError:
        pass
for _ in range(30):
    try:
        subprocess.check_output(["pgrep", "-f", "buun_vbr/build/bin/llama-server"], text=True)
        time.sleep(2)
    except subprocess.CalledProcessError:
        break

print(f"  launching MTP={MODE} with {len(argv)} args")
with open(LOG, "w") as lf:
    subprocess.Popen(argv, stdout=lf, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)

for i in range(180):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8082/health", timeout=5) as r:
            if b'"ok"' in r.read():
                print(f"  healthy after {i*5}s"); sys.exit(0)
    except Exception:
        pass
    time.sleep(5)
print("  NEVER BECAME HEALTHY"); sys.exit(1)
