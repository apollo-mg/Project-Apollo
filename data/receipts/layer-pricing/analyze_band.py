#!/usr/bin/env python3
"""fp16->t8 layer-pricing band: is there a per-(layer,side) price, and is it resolvable?

Dump format (perplexity.cpp:1954): [int32 n_pos][int32 n_chunk][float32 kld[n_chunk*n_pos]]
chunk-major. n_pos = n_ctx-1-first = 2047, so only the SECOND HALF of each 4096 window is
scored -- every scored position sits at 2-4k of KV depth. This is a SHALLOW-CONTEXT table.

THE NULL IS NOT ZERO. anchor_selfcheck.bin is fp16-vs-fp16-base: true KLD is exactly 0 at
every position, yet it ranges +/-7e-5 and is 50.6% NEGATIVE -- GPU run-to-run
nondeterminism (reduction order / atomics). Per-position values are unusable; the signal
(~1e-6) is ~70x smaller than one position's noise.

TWO SEs, AND USING THE WRONG ONE INFLATES EVERY z BY ~8x:
  - the null's SE (7.8e-08) describes only GPU nondeterminism.
  - a CELL also carries chunk-dependent quantization variance, so its SE must come from its
    OWN 8 chunk means. Measured median 6.1e-07 -- cells are 7.9x noisier than the null.
Chunks are the independent unit (positions inside one share a KV history), and for K-vs-V
the LAYER is the replication unit -- the same 8 text chunks recur in every layer, so
pooling 6 layers x 8 chunks as 48 independent deltas is pseudoreplication.
"""
import numpy as np, glob, re, sys, itertools
from scipy.stats import spearmanr, ttest_1samp

DIR      = sys.argv[1] if len(sys.argv) > 1 else "."
RHO_GATE = 0.90   # stated here because no threshold is recorded in METHODOLOGY.
                  # A price TABLE is a rank order; below this the neighbour order is a
                  # coin flip and the table is noise wearing a ranking.

def load(f):
    raw = open(f, "rb").read()
    n_pos, nchk = np.frombuffer(raw[:8], dtype=np.int32)
    return np.frombuffer(raw[8:], dtype=np.float32).reshape(nchk, n_pos).astype(np.float64)

def se(d):                       # SE over chunk means, ddof=1
    cm = d.mean(axis=1); return cm.std(ddof=1)/np.sqrt(len(cm))

null = load(f"{DIR}/anchor_selfcheck.bin")
D    = {re.search(r"cell_(\w+)_t8", f).group(1): load(f)
        for f in glob.glob(f"{DIR}/cells/cell_*.bin")}
tags = sorted(D, key=lambda x: (int(x[:-1]), x))
layers = sorted({int(t[:-1]) for t in D if f"{t[:-1]}v" in D and f"{t[:-1]}k" in D})
print(f"{len(D)} cells | null mean {null.mean():+.3e} SE {se(null):.2e} | "
      f"median cell SE {np.median([se(D[t]) for t in tags]):.2e}\n")

# --- 1. does each cell separate from the null, on its OWN SE? -----------------
clears = 0
for t in tags:
    z = (D[t].mean() - null.mean())/se(D[t]); clears += abs(z) > 1.96
    print(f"  {t:>5} {D[t].mean():10.3e}  SE {se(D[t]):8.2e}  z={z:5.2f}"
          f"{'' if abs(z)>1.96 else '   in the noise'}")
print(f"\n[1] {clears}/{len(D)} cells clear the fp16 null individually at 95%.\n")

# --- 2. K vs V, replicated at the LAYER level --------------------------------
dl = np.array([D[f"{L}k"].mean() - D[f"{L}v"].mean() for L in layers])
t, p = ttest_1samp(dl, 0)
print(f"[2] K-V over {len(dl)} layers: mean {dl.mean():+.3e}  t={t:.2f} on {len(dl)-1} df  "
      f"p={p:.4f}  sign {(dl>0).sum()}/{len(dl)}\n")

# --- 3. is the FINE rank order reproducible? all distinct 4/4 chunk splits ----
rhos = []
for h in itertools.combinations(range(null.shape[0]), null.shape[0]//2):
    if 0 not in h: continue
    o = [c for c in range(null.shape[0]) if c not in h]
    rhos.append(spearmanr(np.array([D[t][list(h)].mean() for t in tags]),
                          np.array([D[t][o].mean()       for t in tags])).statistic)
rhos = np.array(rhos)
m    = np.array([D[t].mean() for t in tags])
gap  = np.median(np.diff(np.sort(m)))/np.median([se(D[t]) for t in tags])
need = null.shape[0]*(3/gap)**2
print(f"[3] rho_half = {rhos.mean():.3f} +/- {rhos.std():.3f} over {len(rhos)} splits "
      f"[{rhos.min():.3f}, {rhos.max():.3f}]   GATE {RHO_GATE} -> "
      f"{'PASS' if rhos.mean() >= RHO_GATE else 'FAIL'}")
print(f"    median adjacent gap {gap:.2f} cell-SE  ->  ~{need:.0f} chunks/cell for 3 SE "
      f"= {need/8*4.1/60:.0f} h/cell, {32*need/8*4.1/60:.0f} h for 32 cells")
