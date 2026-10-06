#!/usr/bin/env python3
"""K5a-K5d (PREREG_KOLIBRI_194 addendum K5): compare two Kolibri-1 GGUFs from different converters without loading a
model. usage: k5_compare.py A.gguf B.gguf  (gguf-py on PYTHONPATH; reads headers and single tensors through mmap)"""
import hashlib, json, sys
import numpy as np
from gguf import GGUFReader, GGMLQuantizationType as T
from gguf.quants import dequantize

A, B = GGUFReader(sys.argv[1]), GGUFReader(sys.argv[2])
SKIP_PREFIX = ("general.", "GGUF.")
SKIP = {"tokenizer.ggml.pre"}
FLOAT = {T.F32, T.F16, T.BF16}


def val(f):
    try:
        v = f.contents()
    except Exception:
        v = [bytes(f.parts[i]).decode("utf-8", "replace") if f.types and f.types[0].name == "STRING"
             else f.parts[i].tolist() for i in f.data]
    if (isinstance(v, list) and len(v) > 16) or (isinstance(v, str) and len(v) > 200):
        return {"len": len(v), "sha256": hashlib.sha256(json.dumps(v, default=str).encode()).hexdigest()[:16]}
    return v


fa = {k: val(f) for k, f in A.fields.items() if not k.startswith(SKIP_PREFIX) and k not in SKIP}
fb = {k: val(f) for k, f in B.fields.items() if not k.startswith(SKIP_PREFIX) and k not in SKIP}
print("== K5a metadata")
bad = 0
for k in sorted(set(fa) | set(fb)):
    eq = fa.get(k, "<absent>") == fb.get(k, "<absent>")
    bad += not eq
    print(f"{'  ' if eq else 'XX'} {k}: A={fa.get(k, '<absent>')} B={fb.get(k, '<absent>')}" if not eq or not isinstance(fa.get(k), dict) else f"   {k}: {fa[k]}")
print(f"K5a: {bad} differing keys of {len(set(fa) | set(fb))}")
print("   (excluded) tokenizer.ggml.pre A=%s B=%s" % (val(A.fields["tokenizer.ggml.pre"]) if "tokenizer.ggml.pre" in A.fields else None,
                                                   val(B.fields["tokenizer.ggml.pre"]) if "tokenizer.ggml.pre" in B.fields else None))

ta = {t.name: t for t in A.tensors}
tb = {t.name: t for t in B.tensors}
print("== K5b tensor list")
only_a, only_b = sorted(set(ta) - set(tb)), sorted(set(tb) - set(ta))
shape_bad = [n for n in sorted(set(ta) & set(tb)) if list(ta[n].shape) != list(tb[n].shape)]
print(f"A {len(ta)} tensors, B {len(tb)}; only in A: {only_a[:10]}; only in B: {only_b[:10]}; shape differs: {shape_bad[:10]}")
types = {}
for n in sorted(set(ta) & set(tb)):
    key = (ta[n].tensor_type.name, tb[n].tensor_type.name)
    types[key] = types.get(key, 0) + 1
print("type pairs (A, B):", {f"{a}/{b}": c for (a, b), c in sorted(types.items())})
print(f"K5b: {'holds' if not (only_a or only_b or shape_bad) else 'FAILS'}")


def deq(t, data=None):
    d = t.data if data is None else data
    return dequantize(np.asarray(d), t.tensor_type).astype(np.float32)


print("== K5c tensors stored as float in both")
worst, exact, n_cmp, fails = 0.0, 0, 0, []
groups = {}
for n in sorted(set(ta) & set(tb)):
    if ta[n].tensor_type not in FLOAT or tb[n].tensor_type not in FLOAT:
        continue
    a, b = deq(ta[n]).ravel(), deq(tb[n]).ravel()
    n_cmp += 1
    g = n.split(".", 2)[-1] if n.startswith("blk.") else n
    tol = 2.0 ** -7 * np.maximum(np.abs(a), np.abs(b)) + 1e-30
    viol = int((np.abs(a - b) > tol).sum())
    rel = float(np.abs(a - b).max() / (np.abs(a).max() + 1e-30))
    worst = max(worst, rel)
    exact += bool(np.array_equal(a, b))
    s = groups.setdefault(g, [0, 0, 0, 0.0])
    s[0] += 1; s[1] += bool(np.array_equal(a, b)); s[2] += viol; s[3] = max(s[3], rel)
    if viol:
        fails.append((n, viol, a.size, rel))
for g, (cnt, ex, viol, rel) in sorted(groups.items()):
    print(f"   {g}: {cnt} tensors, {ex} bit-identical, elements beyond BF16 rounding {viol}, max |a-b|/max|a| {rel:.3g}")
print(f"K5c: {n_cmp} tensors compared, {exact} bit-identical, {len(fails)} with elements beyond BF16 rounding; "
      f"worst normwise rel diff {worst:.3g}; {'holds' if n_cmp and not fails else ('FAILS' if fails else 'NOTHING TO COMPARE')}")
for f in fails[:15]:
    print("   XX", f)

print("== K5d dequantized weights")
picks = []
for cand in ("blk.0.attn_q.weight", "blk.0.attn_qkv.weight", "blk.0.attn_k.weight"):
    if cand in ta and cand in tb:
        picks.append((cand, None)); break
for cand in ("blk.0.ffn_gate_exps.weight", "blk.0.ffn_down_exps.weight", "blk.1.ffn_gate_exps.weight", "blk.1.ffn_down_exps.weight"):
    if cand in ta and cand in tb:
        picks.append((cand, 0))
if not any(p[1] == 0 for p in picks):
    exps = [n for n in sorted(set(ta) & set(tb)) if "_exps.weight" in n][:2]
    picks += [(n, 0) for n in exps]
rs = []
for n, e in picks:
    if e is None:
        a, b = deq(ta[n]), deq(tb[n])
    else:
        a, b = deq(ta[n], ta[n].data[e]), deq(tb[n], tb[n].data[e])
    r = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    rr = float(np.linalg.norm(a - b) / np.linalg.norm(a))
    rs.append(r)
    print(f"   {n}{'' if e is None else f' expert {e}'}: types {ta[n].tensor_type.name}/{tb[n].tensor_type.name}, "
          f"shape {a.shape}, Pearson r {r:.5f}, rel RMS diff {rr:.4f}")
print(f"K5d: min r {min(rs):.5f} -> {'holds' if min(rs) >= 0.95 else ('STRUCTURAL' if min(rs) < 0.5 else 'FAILS')}")
