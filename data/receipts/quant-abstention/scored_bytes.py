#!/usr/bin/env python3
"""Scored bytes and scored bpw per arm (DESIGN: the x-axis is scored bytes, MTP head and mmproj subtracted).

GGUF: sum of tensor bytes, excluding every tensor of the MTP block (the block index whose tensors include
`nextn`; blk.64.* for Qwen3.8-27B). EXL3 (safetensors directories): sum of tensor bytes from the headers,
excluding tensors whose name contains `mtp`. Parameters are counted from the Q8_0 reference's non-MTP tensor
shapes, so bpw = scored_bytes * 8 / scored_params is on one axis for every arm.
Usage: PYTHONPATH=<buun>/gguf-py scored_bytes.py <file-or-dir> ...  (prints JSON lines)
"""
import json, os, re, struct, sys
from pathlib import Path
import numpy as np
from gguf import GGUFReader


def gguf_scored(path):
    r = GGUFReader(path)
    mtp = {int(m.group(1)) for t in r.tensors for m in [re.match(r"blk\.(\d+)\.nextn", t.name)] if m}
    keep = [t for t in r.tensors if not (m := re.match(r"blk\.(\d+)\.", t.name)) or int(m.group(1)) not in mtp]
    return {"scored_bytes": int(sum(int(t.n_bytes) for t in keep)),
            "scored_params": int(sum(int(np.prod(t.shape)) for t in keep)),
            "excluded_blocks": sorted(mtp), "file_bytes": os.path.getsize(path)}


def exl3_scored(d):
    total, excl = 0, 0
    for f in sorted(Path(d).glob("*.safetensors")):
        with open(f, "rb") as fh:
            n = struct.unpack("<Q", fh.read(8))[0]
            hdr = json.loads(fh.read(n))
        for k, v in hdr.items():
            if k == "__metadata__":
                continue
            size = v["data_offsets"][1] - v["data_offsets"][0]
            if "mtp" in k.lower():
                excl += size
            else:
                total += size
    return {"scored_bytes": total, "excluded_mtp_bytes": excl,
            "file_bytes": sum(f.stat().st_size for f in Path(d).glob("*.safetensors"))}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        out = exl3_scored(p) if os.path.isdir(p) else gguf_scored(p)
        print(json.dumps({"path": re.sub(r"^/mnt/TG_2TB/AI/Models/", "", p), **out}), flush=True)
