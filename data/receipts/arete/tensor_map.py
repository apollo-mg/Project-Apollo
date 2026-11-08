#!/usr/bin/env python3
"""PREREG_ARETE.md conversion check (recorded, not a gate): compare the per-tensor quant types of our Arete Q8_0 with the
base Q8_0 the ceiling ran. Prints counts by type for each file and every tensor whose type differs or that only one
file has. Usage: tensor_map.py GGUF_PY_DIR OURS BASE"""
import sys, collections
sys.path.insert(0, sys.argv[1]); import gguf
maps = []
for p in sys.argv[2:4]:
    r = gguf.GGUFReader(p)
    maps.append({t.name: t.tensor_type.name for t in r.tensors})
for name, m in zip(("ours", "base"), maps):
    print(name, len(m), "tensors:", dict(collections.Counter(m.values())))
a, b = maps
only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
print(f"only in ours: {len(only_a)}; only in base: {len(only_b)}; same name, different type: {len(diff)}")
for k in only_a[:10]: print("  ours only:", k, a[k])
for k in only_b[:10]: print("  base only:", k, b[k])
for k in diff[:20]: print("  type differs:", k, a[k], "vs base", b[k])
