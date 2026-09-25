#!/usr/bin/env python3
"""Score PREREG_VBR_RATE_DISTORTION.md (+ Amendment 1: 16k context, 18 chunks, criterion >= 16/18).
Inputs: raw/dumps/<ARM>.kld.bin (int32 n_pos | int32 n_chunk | float32 kld[n_chunk*n_pos]),
raw/traces/<ARM>.vbrtrace.tsv (VBR arms), raw/logs/<ARM>.log.gz (static arms: max 'KV buffer size').
Output: RESULT_s4.json + a printed summary."""
import gzip, itertools, json, re
import numpy as np
from pathlib import Path

HERE = Path(__file__).parent
RAW = HERE / "raw"
N_CTX = 16384
MIB = 1024 * 1024
STATIC = ["Q8", "Q4", "T4", "T3"]
VBR = ["V75", "V55", "V40", "V29", "V22", "V16"]      # budget arms (VF never binds)
TESTS = {"R2": "Q8", "R3": "Q4", "R4": "T3"}

def load(arm):
    b = np.fromfile(RAW / "dumps" / f"{arm}.kld.bin", dtype=np.uint8)
    n_pos, n_chunk = np.frombuffer(b[:8].tobytes(), dtype=np.int32)
    return np.frombuffer(b[8:].tobytes(), dtype=np.float32).astype(np.float64).reshape(n_chunk, n_pos)

def static_mib(arm):
    t = gzip.open(RAW / "logs" / f"{arm}.log.gz", "rt").read()
    return max(float(x) for x in re.findall(r"KV buffer size = *([0-9.]+) MiB", t))

def trace_chunks(arm):
    """Per-chunk rows of the VBR trace: split where the watermark drops (kv-depth method)."""
    rows = []
    for ln in (RAW / "traces" / f"{arm}.vbrtrace.tsv").read_text().splitlines():
        if ln.startswith("#"):
            continue
        ph, bnd, cur, fnv, wm, used, mapped = ln.split("\t")
        rows.append((int(cur), fnv, int(wm), int(used), int(mapped)))
    chunks, cur_chunk, prev_wm = [], [], None
    for r in rows:
        if prev_wm is not None and r[2] < prev_wm:
            chunks.append(cur_chunk); cur_chunk = []
        cur_chunk.append(r); prev_wm = r[2]
    chunks.append(cur_chunk)
    return [c for c in chunks if max(r[2] for r in c) >= N_CTX // 2]

def vbr_mib(arm):
    per = [max(r[4] for r in c) / MIB for c in trace_chunks(arm)]
    return float(np.mean(per)), per

SIGNS = np.array(list(itertools.product((1, -1), repeat=18)), dtype=np.float64)   # 262,144 x 18
def perm_p(d):
    d = np.asarray(d, dtype=np.float64)
    assert len(d) == SIGNS.shape[1]
    obs = abs(d.mean())
    return float((np.abs((SIGNS * d).mean(axis=1)) >= obs - 1e-15).mean())

A = {a: load(a) for a in ["VF"] + STATIC + VBR}
n_chunk, n_pos = A["VF"].shape
C = {a: A[a].mean(axis=1) for a in A}                  # per-chunk mean KLD
alloc = {a: static_mib(a) for a in STATIC}
vbr_per_chunk = {}
for a in VBR:
    alloc[a], vbr_per_chunk[a] = vbr_mib(a)
R = {"n_chunk": int(n_chunk), "n_pos": int(n_pos), "min_attainable_p": 2 / 2 ** n_chunk,
     "alloc_mib": alloc, "vbr_alloc_per_chunk_mib": vbr_per_chunk,
     "mean_kld": {a: float(A[a].mean()) for a in A}}

# R1: VF bit-exact against the f16 reference
R["R1"] = {"max_abs_kld": float(np.abs(A["VF"]).max()), "pass": bool(np.abs(A["VF"]).max() == 0.0)}

# R5: monotone curve
order = sorted(VBR, key=lambda a: alloc[a])
means = [float(A[a].mean()) for a in order]
R["R5"] = {"order_by_alloc": order, "means": means,
           "pass": all(means[i] >= means[i + 1] for i in range(len(means) - 1))}

def interp_curve(a_target):
    """Per-chunk log-log interpolation between the two VBR arms bracketing a_target; None if not bracketed."""
    lo = [a for a in order if alloc[a] <= a_target]
    hi = [a for a in order if alloc[a] >= a_target]
    if not lo or not hi:
        return None, None, None
    L, U = lo[-1], hi[0]
    if L == U:
        return C[L], L, U
    w = (np.log(a_target) - np.log(alloc[L])) / (np.log(alloc[U]) - np.log(alloc[L]))
    return np.exp(np.log(C[L]) + w * (np.log(C[U]) - np.log(C[L]))), L, U

for h, s in TESTS.items():
    k, L, U = interp_curve(alloc[s])
    if k is None:
        R[h] = {"static": s, "verdict": "VOID (not bracketed)"}; continue
    d = k - C[s]
    p = perm_p(d)
    lower = int((d < 0).sum())
    R[h] = {"static": s, "static_alloc_mib": alloc[s], "bracket": [L, U],
            "bracket_alloc_mib": [alloc[L], alloc[U]], "static_mean": float(C[s].mean()),
            "vbr_interp_mean": float(k.mean()), "diff_mean": float(d.mean()), "rel": float(d.mean() / C[s].mean()),
            "chunks_vbr_lower": lower, "p_perm": p,
            "pass": bool(d.mean() < 0 and lower >= 16 and p < 0.05)}
    R[h]["verdict"] = "PASS" if R[h]["pass"] else ("REVERSED" if d.mean() > 0 and p < 0.05 else "FAIL")

# descriptive: T4 as a frontier point, and .73's operating points (bpv -> MiB at 16k: f16 = 1024 MiB = 16 bpv)
k, L, U = interp_curve(alloc["T4"])
R["T4_frontier"] = {"alloc": alloc["T4"], "t4_mean": float(C["T4"].mean()),
                    "vbr_interp_mean": None if k is None else float(k.mean()), "bracket": [L, U]}
R["ops_73"] = {}
for name, bpv in (("floor_t4_4.125bpv", 4.125), ("observed_128k_5.83bpv", 5.83)):
    k, L, U = interp_curve(1024 * bpv / 16)
    R["ops_73"][name] = {"mib": 1024 * bpv / 16, "vbr_interp_mean": None if k is None else float(k.mean()), "bracket": [L, U]}

(HERE / "RESULT_s4.json").write_text(json.dumps(R, indent=1))
print(f"chunks {n_chunk} x {n_pos}; min p {R['min_attainable_p']:.2e}")
for a in sorted(alloc, key=lambda x: -alloc[x]):
    print(f"  {a:4s} {alloc[a]:8.1f} MiB  {alloc[a]/1024*16:5.2f} bpv  mean KLD {A[a].mean():.6f}")
print("R1", R["R1"]); print("R5", R["R5"]["pass"], [round(m, 6) for m in means])
for h in TESTS:
    r = R[h]; print(h, {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items() if k != "bracket_alloc_mib"})
print("T4", R["T4_frontier"]); print("ops_73", R["ops_73"])
