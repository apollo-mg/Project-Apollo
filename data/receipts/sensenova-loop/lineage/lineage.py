"""Weight lineage: cosine similarity and relative change of every same-named, same-shaped tensor (SenseNova vs Qwen3.5-9B),
plus a control: each SenseNova layer's MLP down_proj against Qwen's down_proj at a DIFFERENT layer (shifted by 7)."""
import json, sys, statistics, re
from collections import defaultdict
import torch
from safetensors import safe_open
A, B, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
ma = json.load(open(f"{A}/model.safetensors.index.json"))["weight_map"]
mb = json.load(open(f"{B}/model.safetensors.index.json"))["weight_map"]
fh = {}
def get(root, m, k):
    f = m[k]
    if (root, f) not in fh: fh[(root, f)] = safe_open(f"{root}/{f}", "pt")
    return fh[(root, f)].get_tensor(k).float().flatten()
def cmp(x, y):
    return (torch.dot(x, y) / (x.norm() * y.norm() + 1e-12)).item(), ((x - y).norm() / (y.norm() + 1e-12)).item()
rows, groups = [], defaultdict(list)
for k in sorted(set(ma) & set(mb)):
    if k.startswith("mtp."): continue
    x, y = get(A, ma, k), get(B, mb, k)
    if x.shape != y.shape: rows.append({"tensor": k, "shape_differs": True}); continue
    cos, rel = cmp(x, y)
    rows.append({"tensor": k, "cos": round(cos, 5), "rel_change": round(rel, 5), "numel": x.numel()})
    m = re.match(r"model\.language_model\.layers\.(\d+)\.", k)
    g = ("visual" if k.startswith("model.visual") else f"layer {int(m.group(1)):02d}" if m else k)
    if x.numel() > 4096: groups[g].append(cos)
ctrl = []
for i in range(32):
    j = (i + 7) % 32
    ka, kb = f"model.language_model.layers.{i}.mlp.down_proj.weight", f"model.language_model.layers.{j}.mlp.down_proj.weight"
    ctrl.append(cmp(get(A, ma, ka), get(B, mb, kb))[0])
only_a = sorted(k for k in set(ma) - set(mb) if not k.startswith("mtp."))
summary = {g: round(statistics.mean(v), 4) for g, v in sorted(groups.items())}
json.dump({"groups_mean_cos_matrices": summary, "control_shifted_down_proj_cos": [round(c, 4) for c in ctrl],
           "only_in_sensenova": only_a, "tensors": rows}, open(OUT, "w"), indent=1)
for g, v in summary.items(): print(f"{g:40s} mean cos {v:.4f}")
print(f"control (down_proj, layer i vs i+7): mean cos {statistics.mean(ctrl):.4f}, max {max(ctrl):.4f}")
print("only in SenseNova:", len(only_a), only_a[:4], "...")
print("shape differs:", [r['tensor'] for r in rows if r.get('shape_differs')][:5])
