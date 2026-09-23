#!/usr/bin/env python3
"""Is REAP-320 Q2 a byte-copy prune of THIS UD-Q2_K_XL? Compare kept experts (per manifest) and
non-expert tensors between the pruned split GGUF and the local unpruned split GGUF."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "buun-llama-cpp/gguf-py"))
from gguf import GGUFReader

PRUNED = sorted((Path.home() / "AI/Models/flash_next_reap320_q2/Q2").glob("*.gguf"))
PARENT = sorted((Path.home() / "AI/Models/flashnext_q2").glob("*.gguf"))
MAN = json.load(open(Path.home() / "AI/Models/flash_next_reap320_q2/manifests/seleccion_mass_K320.json"))

def tensors(files):
    out = {}
    for f in files:
        for t in GGUFReader(f).tensors:
            out[t.name] = t
    return out

P, Q = tensors(PRUNED), tensors(PARENT)
h = lambda b: hashlib.sha256(memoryview(b).cast("B")).hexdigest()
res = {"expert_checks": 0, "expert_mismatch": [], "dense_checks": 0, "dense_mismatch": [],
       "missing_in_parent": [], "shape_odd": []}
for name, tp in P.items():
    tq = Q.get(name)
    if tq is None:
        res["missing_in_parent"].append(name); continue
    if "_exps" in name:
        layer = name.split(".")[1]
        keep = MAN[str(int(layer))]
        ne_p, ne_q = int(tp.shape[-1]), int(tq.shape[-1])
        if ne_p != len(keep) or ne_q != 512:
            res["shape_odd"].append((name, ne_p, ne_q, len(keep))); continue
        bp, bq = tp.data.reshape(-1), tq.data.reshape(-1)
        sp, sq = bp.nbytes // ne_p, bq.nbytes // ne_q
        vp, vq = bp.view("u1"), bq.view("u1")
        for j in sorted({0, 1, ne_p // 2, ne_p - 1}):
            src = keep[j]
            if h(vp[j * sp:(j + 1) * sp]) != h(vq[src * sq:(src + 1) * sq]):
                res["expert_mismatch"].append((name, j, src))
            res["expert_checks"] += 1
    else:
        if tp.data.nbytes > 64 * 2**20:   # hash large dense tensors by head+tail 16 MiB
            a, b = tp.data.reshape(-1).view("u1"), tq.data.reshape(-1).view("u1")
            same = a.nbytes == b.nbytes and h(a[:2**24]) == h(b[:2**24]) and h(a[-2**24:]) == h(b[-2**24:])
        else:
            same = h(tp.data) == h(tq.data)
        res["dense_checks"] += 1
        if not same:
            res["dense_mismatch"].append(name)
print(json.dumps({k: (v if not isinstance(v, list) else (len(v), v[:6])) for k, v in res.items()}, indent=1))
