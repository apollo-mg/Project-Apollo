import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path.home() / "buun-llama-cpp/gguf-py"))
from gguf import GGUFReader
def T(files):
    o = {}
    for f in files:
        for t in GGUFReader(f).tensors: o[t.name] = t
    return o
P = T(sorted((Path.home()/"AI/Models/flash_next_reap320_q2/Q2").glob("*.gguf")))
Q = T(sorted((Path.home()/"AI/Models/flashnext_q2").glob("*.gguf")))
MAN = json.load(open(Path.home()/"AI/Models/flash_next_reap320_q2/manifests/seleccion_mass_K320.json"))
ok = bad = 0; ex = []
for n, tp in P.items():
    if not n.endswith("ffn_gate_inp.weight"): continue
    tq = Q[n]; keep = MAN[str(int(n.split(".")[1]))]
    a, b = np.asarray(tp.data), np.asarray(tq.data)
    if tp.tensor_type != tq.tensor_type: ex.append((n, "type", str(tp.tensor_type), str(tq.tensor_type)))
    # rows = experts: axis 0 of the numpy view is the expert dim for a [n_embd, n_expert] ggml tensor
    if a.shape[0] == len(keep) and np.array_equal(a, b[keep]): ok += 1
    else: bad += 1; ex.append((n, a.shape, b.shape))
print({"routers_exact_row_subset": ok, "routers_other": bad, "examples": ex[:3]})
