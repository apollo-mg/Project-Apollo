#!/usr/bin/env python3
"""Compare selected tensors between Hugging Face safetensors repos by HTTP range requests (no full download).

  hf_tensor_drift.py REPO_A REPO_B [REPO_C ...] --tensors NAME [NAME ...] [--rows N] [--cache DIR]

For each tensor: dtype and shape per repo, then pairwise cosine similarity and relative L2 difference
||a - b|| / ||a||. FP8 e4m3 weights with a `<name>_scale_inv` (128x128 block) companion are dequantized. Large 2-D
tensors can be cut to their first N rows (--rows) so a comparison costs megabytes. Repos without a
model.safetensors.index.json have every shard header read (a few KB each) to build the map.
"""
import argparse, json, struct, sys, urllib.request
from pathlib import Path
import numpy as np

HF = "https://huggingface.co"


def get(url, start=None, end=None):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"} if start is not None else {})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def shard_list(repo):
    info = json.loads(get(f"{HF}/api/models/{repo}"))
    return sorted(s["rfilename"] for s in info["siblings"] if s["rfilename"].endswith(".safetensors"))


def header(repo, shard, cache):
    f = cache / (repo.replace("/", "__") + "__" + shard + ".hdr.json")
    if f.exists():
        return json.loads(f.read_text())
    url = f"{HF}/{repo}/resolve/main/{shard}"
    n = struct.unpack("<Q", get(url, 0, 7))[0]
    h = json.loads(get(url, 8, 8 + n - 1))
    h["__data_start__"] = 8 + n
    f.write_text(json.dumps(h))
    return h


def tensor_map(repo, cache):
    f = cache / (repo.replace("/", "__") + "__map.json")
    if f.exists():
        return json.loads(f.read_text())
    try:
        wm = json.loads(get(f"{HF}/{repo}/resolve/main/model.safetensors.index.json"))["weight_map"]
    except Exception:
        wm = {}
        for s in shard_list(repo):
            for k in header(repo, s, cache):
                if k not in ("__metadata__", "__data_start__"):
                    wm[k] = s
    f.write_text(json.dumps(wm))
    return wm


DT = {"BF16": 2, "F16": 2, "F32": 4, "F8_E4M3": 1}


def fp8_e4m3_to_f32(b):
    b = b.astype(np.uint16)
    s = (b >> 7) & 1; e = (b >> 3) & 0xF; m = b & 0x7
    sub = (e == 0)
    v = np.where(sub, (m / 8.0) * 2.0 ** -6, (1 + m / 8.0) * 2.0 ** (e.astype(np.int32) - 7))
    v = np.where((e == 0xF) & (m == 0x7), np.nan, v)
    return np.where(s == 1, -v, v).astype(np.float32)


def read(repo, name, rows, cache):
    wm = tensor_map(repo, cache)
    if name not in wm:
        return None, None
    h = header(repo, wm[name], cache)
    meta = h[name]; dt = meta["dtype"]; shape = meta["shape"]; a, b = meta["data_offsets"]
    nb = DT[dt]
    n_rows = shape[0] if len(shape) > 0 else 1
    row_elems = int(np.prod(shape[1:])) if len(shape) > 1 else (shape[0] if shape else 1)
    take = min(rows, n_rows) if (rows and len(shape) > 1) else n_rows
    nbytes = (take * row_elems * nb) if len(shape) > 1 else (b - a)
    raw = get(f"{HF}/{repo}/resolve/main/{wm[name]}", h["__data_start__"] + a, h["__data_start__"] + a + nbytes - 1)
    if dt == "BF16":
        x = (np.frombuffer(raw, np.uint16).astype(np.uint32) << 16).view(np.float32)
    elif dt == "F16":
        x = np.frombuffer(raw, np.float16).astype(np.float32)
    elif dt == "F32":
        x = np.frombuffer(raw, np.float32)
    else:
        x = fp8_e4m3_to_f32(np.frombuffer(raw, np.uint8))
        sname = name + "_scale_inv"
        if sname in wm:                      # 128x128 block scales
            s, _ = read(repo, sname, None, cache)
            x = x.reshape(take, row_elems)
            bi = (np.arange(take) // 128)[:, None]; bj = (np.arange(row_elems) // 128)[None, :]
            x = x * s.reshape(-1, (row_elems + 127) // 128)[bi, bj]
    x = x.reshape(take, row_elems) if len(shape) > 1 else x
    return x, {"dtype": dt, "shape": shape, "rows_read": take if len(shape) > 1 else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+"); ap.add_argument("--tensors", nargs="+", required=True)
    ap.add_argument("--rows", type=int, default=256); ap.add_argument("--cache", default="/tmp/hf_drift_cache")
    a = ap.parse_args(); cache = Path(a.cache); cache.mkdir(parents=True, exist_ok=True)
    out = []
    for t in a.tensors:
        vals = {}
        for r in a.repos:
            x, m = read(r, t, a.rows, cache)
            vals[r] = (x, m)
            print(f"{t}  {r}: " + (f"{m['dtype']} {m['shape']} rows_read={m['rows_read']}" if m else "MISSING"), flush=True)
        reps = [r for r in a.repos if vals[r][0] is not None]
        for i in range(len(reps)):
            for j in range(i + 1, len(reps)):
                x, y = vals[reps[i]][0].ravel().astype(np.float64), vals[reps[j]][0].ravel().astype(np.float64)
                if x.shape != y.shape:
                    print(f"   {reps[i]} vs {reps[j]}: shape differs"); continue
                cos = float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))
                rel = float(np.linalg.norm(x - y) / np.linalg.norm(x))
                same = float(np.mean(x == y))
                print(f"   {reps[i]} vs {reps[j]}: cos={cos:.6f} rel_l2={rel:.4f} identical_elems={same:.4f}")
                out.append({"tensor": t, "a": reps[i], "b": reps[j], "cos": cos, "rel_l2": rel, "identical": same})
    print("JSON " + json.dumps(out))


if __name__ == "__main__":
    main()
