#!/usr/bin/env python3
"""apollo-fit — size a local model against the VRAM you ACTUALLY have.

WHY THIS EXISTS
  The runtime's own fit logic cannot be trusted on a display-driving card. Measured
  2026-08-18 on an RX 9070 XT with a live desktop, at the same instant:

      hipMemGetInfo (what llama.cpp asks) : 16,036 MiB free
      sysfs mem_info_vram_used            : 13,306 MiB free  (2,997 MiB in use)

  hipMemGetInfo accounted for 268 of 2,997 MiB actually allocated -- it reports roughly
  "total minus my own allocations", not system-wide free memory. llama.cpp calls the correct
  API; the driver answers wrongly. Anything derived from it (--fit, VBR's auto budget) is
  therefore optimistic by however much else is on the card, and the resulting OOM lands at
  DEPTH rather than at load. NVIDIA behaviour is UNVERIFIED, so this tool reads ground truth
  on both and never asks the runtime.

  It also refuses to compute KV cost from architecture parameters. Measured on
  Qwen3.8-27B: the naive n_layer x n_head_kv x (d_k+d_v) formula gives 256 KiB/token; the
  real figure is 64 KiB/token, because only ~16 of its 64 layers carry a KV cache at all
  (the rest are Lightning/linear attention with O(1) state). A 4x error. Hybrid models are
  common now, so bytes/token is measured, cached, or refused -- never guessed.

USAGE
  apollo-fit.py --vram                       # what is actually free, right now
  apollo-fit.py --model M.gguf --measure --bin ./llama-cli
  apollo-fit.py --model M.gguf --ctx 260000 --bpv 6
"""
import argparse, glob, json, os, re, subprocess, sys

CACHE = os.path.expanduser("~/.cache/apollo-fit-kv.json")
MiB = 1024**2

def _read(p):
    try:    return int(open(p).read().strip())
    except Exception: return None

def vram():
    """Ground-truth VRAM per device. sysfs on amdgpu, nvidia-smi on NVIDIA. Never the runtime."""
    devs = []
    for tot in sorted(glob.glob("/sys/class/drm/card*/device/mem_info_vram_total")):
        t = _read(tot); u = _read(tot.replace("_total", "_used"))
        if t and u is not None:
            devs.append({"dev": f"amdgpu:{tot.split('/')[4]}", "total": t//MiB,
                         "used": u//MiB, "free": (t-u)//MiB})
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.total,memory.used",
                              "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=15).stdout.strip()
        for line in filter(None, out.splitlines()):
            i, t, u = [x.strip() for x in line.split(",")]
            devs.append({"dev": f"cuda:{i}", "total": int(t), "used": int(u),
                         "free": int(t)-int(u)})
    except Exception:
        pass
    return devs

def measure_bpt(binary, model, ctxs=(4096, 16384)):
    """bytes/token @f16, from the SLOPE of two loads.

    Two points, not one: a fixed per-context overhead exists (~128 KiB on turbo KV types),
    and reading a single context size as a rate is what produced a retracted finding in this
    project. The slope cancels it."""
    pts = {}
    for c in ctxs:
        env = dict(os.environ, TURBO_AUTO_ASYMMETRIC="0")
        try:
            r = subprocess.run([binary, "-m", model, "-ngl", "99", "-c", str(c),
                                "-ctk", "f16", "-ctv", "f16", "--no-warmup",
                                "-n", "1", "-p", "x", "--temp", "0", "--verbose"],
                               capture_output=True, text=True, timeout=900, env=env)
        except Exception as e:
            print(f"  load at c={c} failed: {e}", file=sys.stderr); return None
        blob = r.stdout + r.stderr
        vals = [float(x) for x in re.findall(r"KV buffer size *= *([0-9.]+) MiB", blob)]
        if not vals:
            # fall back to the memory-breakdown table: "... = model + context + compute"
            m = re.search(r"\|\s*-\s*\S+[^|]*\|\s*\d+\s*=\s*\d+\s*\+\s*\(\s*\d+\s*=\s*\d+\s*\+\s*(\d+)\s*\+", blob)
            if m: vals = [float(m.group(1))]
        if not vals:
            print(f"  no KV size found at c={c} (tried KV-buffer line and breakdown table)",
                  file=sys.stderr); return None
        # a reference + a quant context may both be built; take the LAST device-group
        pts[c] = sum(vals[len(vals)//2:]) if len(vals) > 1 and len(vals) % 2 == 0 else sum(vals)
    (c1, m1), (c2, m2) = sorted(pts.items())
    if c2 == c1: return None
    return (m2 - m1) * MiB / (c2 - c1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vram", action="store_true", help="report real VRAM and exit")
    ap.add_argument("--model"); ap.add_argument("--bin")
    ap.add_argument("--measure", action="store_true", help="measure bytes/token (needs --bin)")
    ap.add_argument("--bpt", type=float, help="bytes/token @f16, if already known")
    ap.add_argument("--ctx", type=int, default=64000)
    ap.add_argument("--bpv", type=float, default=6.0)
    ap.add_argument("--reserve", type=float, default=1.0, help="GiB held back for desktop growth")
    ap.add_argument("--compute", type=float, default=0.8, help="GiB for compute buffers")
    a = ap.parse_args()

    devs = vram()
    if not devs:
        print("no GPUs found via sysfs or nvidia-smi", file=sys.stderr); sys.exit(1)
    print("VRAM (ground truth — NOT the runtime's view):")
    for d in devs:
        print(f"  {d['dev']:<14} total {d['total']:>6} MiB   used {d['used']:>6}   free {d['free']:>6}")
    tot_free = sum(d["free"] for d in devs)
    print(f"  {'TOTAL FREE':<14} {tot_free:>6} MiB  ({tot_free/1024:.2f} GiB)")
    if a.vram or not a.model: return

    cache = {}
    if os.path.exists(CACHE):
        try: cache = json.load(open(CACHE))
        except Exception: pass
    key = os.path.basename(a.model)
    bpt = a.bpt or cache.get(key)
    if a.measure:
        if not a.bin: print("--measure needs --bin", file=sys.stderr); sys.exit(2)
        print(f"\nmeasuring bytes/token for {key} (two loads, taking the slope)...")
        bpt = measure_bpt(a.bin, a.model)
        if bpt:
            cache[key] = bpt
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            json.dump(cache, open(CACHE, "w"), indent=1)
    if not bpt:
        print("\nNo bytes/token for this model. Run with --measure --bin <llama-cli>, or pass"
              "\n--bpt. This tool will NOT guess it from architecture parameters: the naive"
              "\nformula is 4x wrong on hybrid models (measured on Qwen3.8-27B).", file=sys.stderr)
        sys.exit(3)

    wgt = os.path.getsize(a.model) / 1024**3 if os.path.exists(a.model) else 0.0
    pool = tot_free/1024 - a.reserve - a.compute
    kv   = a.ctx * bpt * (a.bpv/16) / 1024**3
    left = pool - wgt

    print(f"\nmodel file            : {wgt:.2f} GiB")
    print(f"bytes/token @f16      : {bpt:,.0f}  ({bpt/1024:.1f} KiB)"
          f"{'  [measured]' if a.measure else '  [cached]'}")
    print(f"usable pool           : {tot_free/1024:.2f} free - {a.reserve} reserve"
          f" - {a.compute} compute = {pool:.2f} GiB")
    print(f"target                : {a.ctx:,} tokens @ {a.bpv} bits/value")
    print(f"KV needed             : {kv:.2f} GiB")
    print(f"weights + KV          : {wgt+kv:.2f} GiB vs {pool:.2f} available")
    if wgt + kv <= pool:
        print(f"\n  FITS — headroom {pool-wgt-kv:.2f} GiB")
        print(f"  VBR_BUDGET_MIB={int(kv*1024)}   # pin it; do NOT let VBR auto-size")
    else:
        print(f"\n  DOES NOT FIT — short by {wgt+kv-pool:.2f} GiB")
        if left > 0:
            print(f"  at this weight, max context @{a.bpv}bpv : {left*1024**3/(bpt*a.bpv/16):,.0f} tokens")
            need = a.ctx*bpt/1024**3
            print(f"  or reach {a.ctx:,} by dropping KV to {16*left/need:.2f} bits/value")
    print(f"\n  (max context if you spent the WHOLE pool on KV @{a.bpv}bpv: "
          f"{pool*1024**3/(bpt*a.bpv/16):,.0f} tokens)")

if __name__ == "__main__":
    main()
