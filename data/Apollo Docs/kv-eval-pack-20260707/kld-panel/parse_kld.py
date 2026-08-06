#!/usr/bin/env python3
# Per-depth KLD panel from a directory of llama-perplexity --kl-divergence logs.
# Log naming: <PREFIX><id>_<depth>.log  (one log per {candidate id} x {context depth}).
# Override via env: LOGDIR=... PREFIX=... DEPTHS=2048,8192,16384,32768 ./parse_kld.py
import re, glob, os, sys
from collections import defaultdict

LOGDIR = os.environ.get("LOGDIR", "./logs")
DEPTHS = [int(x) for x in os.environ.get("DEPTHS", "2048,8192,16384,32768").split(",")]
PREFIX = os.environ.get("PREFIX", "cell_")

def parse(path):
    t = open(path, errors="ignore").read()
    g = {}
    def grab(label, key):
        m = re.search(rf"{re.escape(label)}\s*:\s*(-?[0-9.]+)", t)
        if m: g[key] = float(m.group(1))
    grab("Mean    KLD", "mean")
    grab("Maximum KLD", "max")
    grab("99.9%   KLD", "p999")
    grab("99.0%   KLD", "p99")
    grab("95.0%   KLD", "p95")
    grab("Median  KLD", "median")
    # RMS dp and Same top p (last occurrence in summary block)
    m = re.search(r"RMS Δp\s*:\s*([0-9.]+)", t);      g["rms"]  = float(m.group(1)) if m else None
    m = re.search(r"Same top p:\s*([0-9.]+)", t);     g["same"] = float(m.group(1)) if m else None
    if g.get("same") is not None: g["flip"] = 100.0 - g["same"]
    return g if "mean" in g else None

# book -> depth -> stats
data = defaultdict(dict)
for path in glob.glob(os.path.join(LOGDIR, PREFIX + "*.log")):
    fn = os.path.basename(path)
    m = re.match(rf"{PREFIX}(\d+)_(\d+)\.log", fn)
    if not m: continue
    book, depth = int(m.group(1)), int(m.group(2))
    if depth not in DEPTHS: continue
    st = parse(path)
    if st: data[book][depth] = st

books = sorted(data)
def have_all(b): return all(d in data[b] for d in DEPTHS)
full = [b for b in books if have_all(b)]
print(f"books parsed: {len(books)}, with all 4 depths: {len(full)}\n")

STATS = ["mean","median","p95","p99","p999","max","rms","flip"]
def depthmean(b, k):
    vals = [data[b][d].get(k) for d in DEPTHS if data[b].get(d) and data[b][d].get(k) is not None]
    return sum(vals)/len(vals) if vals else None

# ---- leaderboards (lower=better for KLD/rms/flip) ----
def lb(key, depth=None, n=8, label=""):
    rows=[]
    for b in full:
        v = data[b][depth][key] if depth else depthmean(b,key)
        if v is not None: rows.append((v,b))
    rows.sort()
    print(f"--- best {label or key} {'@'+str(depth) if depth else '(depth-mean)'} ---")
    for v,b in rows[:n]:
        print(f"  iter{b:03d}  {v:.5f}")
    print()

print("="*64); print("LEADERBOARDS"); print("="*64)
lb("mean", None, 8, "MEAN-KLD (avg across depths)")
lb("median", None, 8, "MEDIAN-KLD")
lb("p99", None, 8, "P99-KLD (tail)")
lb("p999", None, 8, "P99.9-KLD (deep tail)")
lb("mean", 32768, 8, "MEAN-KLD @32k (deep)")
lb("flip", 32768, 8, "FLIP @32k")

# ---- full panel for the 4 KLD-maxxed axis winners ----
def winner(key, depth=None):
    best=None
    for b in full:
        v = data[b][depth][key] if depth else depthmean(b,key)
        if v is None: continue
        if best is None or v < best[0]: best=(v,b)
    return best[1]
axes = {
  "MEAN (depth-avg)": winner("mean"),
  "MEDIAN (depth-avg)": winner("median"),
  "P99 (depth-avg)": winner("p99"),
  "DEEP (mean@32k)": winner("mean",32768),
}
print("="*64); print("THE 4 KLD-MAXXED CANDIDATES — full per-depth panel"); print("="*64)
for axis,b in axes.items():
    print(f"\n### {axis} winner = iter{b:03d}")
    print(f"{'depth':>7} {'meanKLD':>9} {'median':>9} {'p95':>9} {'p99':>9} {'p99.9':>9} {'maxKLD':>9} {'RMSdp%':>7} {'flip%':>6}")
    for d in DEPTHS:
        s=data[b][d]
        print(f"{d:>7} {s['mean']:>9.5f} {s['median']:>9.5f} {s['p95']:>9.5f} {s['p99']:>9.5f} {s['p999']:>9.4f} {s['max']:>9.3f} {s['rms']:>7.3f} {s.get('flip',0):>6.3f}")
    print(f"{'AVG':>7} {depthmean(b,'mean'):>9.5f} {depthmean(b,'median'):>9.5f} {depthmean(b,'p95'):>9.5f} {depthmean(b,'p99'):>9.5f} {depthmean(b,'p999'):>9.4f}")

# unique set
uniq = sorted(set(axes.values()))
print(f"\n>>> distinct KLD-maxxed books: {['iter%03d'%b for b in uniq]}")
