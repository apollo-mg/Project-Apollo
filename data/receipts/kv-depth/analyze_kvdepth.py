#!/usr/bin/env python3
"""Score PREREG_KV_DEPTH_MATCHED_ALLOCATION.md (with Amendments 1-2) from the TURBO_KLD_DUMP files.

Dump layout (perplexity.cpp:2121-2140): int32 n_pos, int32 n_chunk, float32[n_chunk*n_pos] chunk-major.
Index i in a chunk = the logit at absolute position FIRST+i (FIRST = n_ctx/2 = 16384).
"""
import itertools, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
N_CTX, FIRST, BATCH = 32768, 16384, 512
MIB = 1024 * 1024

# allocation at 32k: static from the logged 'KV buffer size'; frozen VBR from the trace (below)
STATIC_MIB = {"C0": 1024.0, "Q8": 544.0, "T8": 520.12, "KR": 416.0, "VR": 416.0,
              "Q4": 288.0, "T4": 264.12, "T3": 208.12}


def load(arm):
    b = (RAW / f"{arm}.kld.bin").read_bytes()
    n_pos, n_chunk = np.frombuffer(b[:8], dtype=np.int32)
    a = np.frombuffer(b[8:], dtype=np.float32).astype(np.float64)
    assert a.size == n_pos * n_chunk, (arm, a.size, n_pos, n_chunk)
    return a.reshape(n_chunk, n_pos)


def trace_chunks(arm):
    """Per-chunk rows of the VBR trace: split where the watermark drops."""
    rows = []
    for ln in (RAW / f"{arm}.vbrtrace.tsv").read_text().splitlines():
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
    # the first segment is the warm-up (a lone 256-cell boundary) when present
    chunks = [c for c in chunks if max(r[2] for r in c) >= N_CTX // 2]
    return chunks


def knees(arm):
    """Absolute position where the first degraded batch starts, per chunk (None = never)."""
    out = []
    for c in trace_chunks(arm):
        base_cur = c[0][0]
        k = next((r[3] for r in c if r[0] > base_cur), None)
        out.append(k)
    return out


def max_mapped_mib(arm):
    return [max(r[4] for r in c) / MIB for c in trace_chunks(arm)]


def perm_p(chunk_diffs):
    """Exact two-sided sign-flip permutation test on chunk-level paired mean differences."""
    d = np.asarray(chunk_diffs, dtype=np.float64)
    obs = abs(d.mean())
    n = len(d)
    cnt = 0
    for signs in itertools.product((1, -1), repeat=n):
        if abs((d * signs).mean()) >= obs - 1e-15:
            cnt += 1
    return cnt / 2 ** n


def boot_ci(chunk_diffs, n=20000, seed=0):
    rng = np.random.default_rng(seed)
    d = np.asarray(chunk_diffs)
    m = rng.choice(d, size=(n, len(d)), replace=True).mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def paired(a, b):
    """a - b per chunk (mean over the scored window), with exact p and descriptive CI."""
    diffs = (A[a] - A[b]).mean(axis=1)
    return {"a": a, "b": b, "mean_a": float(A[a].mean()), "mean_b": float(A[b].mean()),
            "diff": float(diffs.mean()), "rel": float(diffs.mean() / A[b].mean()),
            "chunks_a_lower": int((diffs < 0).sum()), "n_chunks": len(diffs),
            "p_perm": perm_p(diffs), "ci95_boot_descriptive": boot_ci(diffs)}


ARMS = ["C0", "C1", "Q8", "Q4", "T4", "T3", "T8", "KR", "VR", "VK", "V8", "V4",
        "C1F", "VKF", "V8F", "V4F", "V8C", "V4C"]
A = {a: load(a) for a in ARMS}
n_chunk, n_pos = A["C0"].shape
assert all(A[a].shape == (n_chunk, n_pos) for a in ARMS)
R = {"n_chunk": int(n_chunk), "n_pos": int(n_pos), "min_attainable_p": 2 / 2 ** n_chunk}

# ---- gates
R["gate_C0_floor_mean"] = float(A["C0"].mean())
R["gate_C0_vs_Q8_ratio"] = float(A["C0"].mean() / A["Q8"].mean())
frozen_alloc = {a: max_mapped_mib(a) for a in ("C1F", "VKF", "V8F", "V4F", "V8C", "V4C")}
R["frozen_max_mapped_mib_per_chunk"] = frozen_alloc
R["alloc_match"] = {
    "V8F_vs_Q8": max(frozen_alloc["V8F"]) / STATIC_MIB["Q8"] - 1,
    "V4F_vs_Q4": max(frozen_alloc["V4F"]) / STATIC_MIB["Q4"] - 1,
    "V8C_vs_Q8": max(frozen_alloc["V8C"]) / STATIC_MIB["Q8"] - 1,
    "V4C_vs_Q4": max(frozen_alloc["V4C"]) / STATIC_MIB["Q4"] - 1}
R["C1F_vs_C0_max_abs"] = float(np.abs(A["C1F"] - A["C0"]).max())
R["C1F_vs_C0_mean_diff"] = float((A["C1F"] - A["C0"]).mean())

# ---- H1: VKF == C1F at every scored position before VKF's knee, per chunk
kn = knees("VKF")
assert len(kn) == n_chunk, (len(kn), n_chunk)
h1_max, h1_npos = 0.0, 0
for ci, k in enumerate(kn):
    upto = n_pos if k is None else max(0, k - FIRST)
    if upto:
        h1_max = max(h1_max, float(np.abs(A["VKF"][ci, :upto] - A["C1F"][ci, :upto]).max()))
        h1_npos += upto
R["H1"] = {"knees_abs_pos": kn, "pre_knee_positions": h1_npos, "max_abs_diff": h1_max,
           "pass": h1_max <= 1e-6}
# descriptive: post-knee cost of VKF relative to C1F
post = [(A["VKF"][ci, k - FIRST:] - A["C1F"][ci, k - FIRST:]).mean() for ci, k in enumerate(kn) if k]
R["H1_post_knee_mean_excess_vs_C1F"] = float(np.mean(post)) if post else None

# ---- H2-H3 scored on the trimmed arms (Amendment 3); the F arms are VOID (alloc gate), descriptive only
R["H2_void_V8F"] = paired("V8F", "Q8")
R["H3_void_V4F"] = paired("V4F", "Q4")
R["H2"] = paired("V8C", "Q8")
R["H3"] = paired("V4C", "Q4")
R["H2"]["alloc_ok"] = -0.02 <= R["alloc_match"]["V8C_vs_Q8"] <= 0
R["H3"]["alloc_ok"] = -0.02 <= R["alloc_match"]["V4C_vs_Q4"] <= 0
R["H4"] = paired("VR", "KR")
for h in ("H2", "H3", "H4"):
    R[h]["pass"] = R[h]["diff"] < 0 and R[h]["p_perm"] < 0.05 and R[h].get("alloc_ok", True)

# ---- H5: slope of per-1k-bin (Q4 - Q8), per chunk
bins = np.arange(0, n_pos, 1024)
def binned(x):
    return np.array([x[:, s:s + 1024].mean(axis=1) for s in bins]).T  # chunk x bin
d45 = binned(A["Q4"]) - binned(A["Q8"])
xc = (bins + 512 + FIRST).astype(float)
slopes = [np.polyfit(xc, d45[c], 1)[0] for c in range(n_chunk)]
R["H5"] = {"slope_per_1k_tokens_mean": float(np.mean(slopes) * 1024),
           "chunks_positive": int((np.array(slopes) > 0).sum()),
           "p_perm": perm_p(slopes)}
R["H5"]["pass"] = R["H5"]["slope_per_1k_tokens_mean"] > 0 and R["H5"]["p_perm"] < 0.05

# ---- descriptive: every arm, frontier, per-bin curves
alloc = dict(STATIC_MIB)
alloc.update({a: max(v) for a, v in frozen_alloc.items()})
R["arms"] = {a: {"mean_kld": float(A[a].mean()), "alloc_mib": alloc.get(a),
                 "p99_kld": float(np.percentile(A[a], 99)),
                 "chunk_means": [float(x) for x in A[a].mean(axis=1)]} for a in ARMS}
R["bins_abs_start"] = [int(b + FIRST) for b in bins]
R["bin_curves"] = {a: [float(x) for x in binned(A[a]).mean(axis=0)] for a in ARMS}

out = HERE / "RESULT_kvdepth.json"
out.write_text(json.dumps(R, indent=1))
print(json.dumps({k: R[k] for k in R if k not in ("bin_curves", "arms", "bins_abs_start")}, indent=1))
print("\narm   alloc_MiB   mean_KLD     p99")
for a in sorted(ARMS, key=lambda a: -(alloc.get(a) or 0)):
    r = R["arms"][a]
    print(f"{a:4s} {str(round(r['alloc_mib'],1)) if r['alloc_mib'] else '  (dyn)':>9s}  {r['mean_kld']:.6f}  {r['p99_kld']:.5f}")
