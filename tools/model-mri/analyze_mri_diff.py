#!/usr/bin/env python3
"""Model MRI diff: base (Qwen3.6-35B-A3B) vs coder fine-tune (Cyber-Tiel), same corpus, same quant.
Token-aligned routing preservation = did the fine-tune re-route (send tokens to different experts)
or keep routing and just change what the experts contain?"""
import struct, sys, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

K = 8
SP = sys.argv[1] if len(sys.argv) > 1 else "."

def load(path):
    out = {}
    with open(path, "rb") as f:
        while True:
            h = f.read(12)
            if len(h) < 12: break
            layer, ne, nt = struct.unpack("<iii", h)
            out[layer] = np.frombuffer(f.read(4*ne*nt), dtype=np.float32).reshape(nt, ne)
    return out

def topk(p):  # [nt,ne] -> list of top-K sets per token
    idx = np.argpartition(-p, K, axis=1)[:, :K]
    return [set(r.tolist()) for r in idx]

def util(layers):  # [nlayer, ne] fraction of tokens with expert in top-K
    L = sorted(layers); ne = layers[L[0]].shape[1]
    U = np.zeros((len(L), ne))
    for i, l in enumerate(L):
        idx = np.argpartition(-layers[l], K, axis=1)[:, :K]
        for r in idx: U[i, r] += 1
        U[i] /= layers[l].shape[0]
    return U

def diff(base, ct, name):
    L = sorted(set(base) & set(ct))
    # token alignment check
    mism = [l for l in L if base[l].shape[0] != ct[l].shape[0]]
    if mism:
        print(f"  [{name}] TOKEN COUNT MISMATCH at layers {mism[:3]} "
              f"(base {base[L[0]].shape[0]} vs ct {ct[L[0]].shape[0]}) -> tokenizers differ, "
              f"per-token diff invalid; aggregate only")
        return None
    preserve = []
    for l in L:
        bt, cs = topk(base[l]), topk(ct[l])
        preserve.append(np.mean([len(bt[t] & cs[t]) / K for t in range(len(bt))]))
    preserve = np.array(preserve)
    Ub, Uc = util(base), util(ct)
    util_l1 = np.abs(Ub - Uc).sum(axis=1) / 2  # per-layer total-variation of utilization
    order = np.argsort(preserve)
    print(f"\n== {name}: base vs Cyber-Tiel routing preservation ==")
    print(f"  mean top-{K} preservation: {preserve.mean():.3f}  (1.0 = identical routing, 0 = fully rewired)")
    print(f"  range [{preserve.min():.2f} (L{L[int(order[0])]}), {preserve.max():.2f} (L{L[int(order[-1])]})]")
    print(f"  most-rewired layers: " + ", ".join(f"L{L[j]}={preserve[j]:.2f}" for j in order[:4]))
    print(f"  most-preserved layers: " + ", ".join(f"L{L[j]}={preserve[j]:.2f}" for j in order[::-1][:4]))
    print(f"  mean utilization shift (TV per layer): {util_l1.mean():.3f}")
    return dict(L=L, preserve=preserve, util_l1=util_l1)

def main():
    res = {}
    for kind in ("code", "prose"):
        base = load(f"{SP}/base_{kind}.bin")
        ct   = load(f"{SP}/mri_{kind}.bin")
        res[kind] = diff(base, ct, kind)
    if any(v is None for v in res.values()): return
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    for kind, color in (("code", "#e6550d"), ("prose", "#3182bd")):
        r = res[kind]
        ax[0].plot(r["preserve"], r["L"], label=kind, color=color)
        ax[1].plot(r["util_l1"], r["L"], label=kind, color=color)
    ax[0].invert_yaxis(); ax[0].set_xlabel(f"top-{K} routing preservation (base vs coder)")
    ax[0].set_ylabel("layer"); ax[0].set_title("How much did the coder fine-tune keep base routing?")
    ax[0].axvline(1.0, ls=":", color="gray"); ax[0].legend(); ax[0].grid(alpha=0.3); ax[0].set_xlim(0,1)
    ax[1].invert_yaxis(); ax[1].set_xlabel("utilization shift (total variation)")
    ax[1].set_ylabel("layer"); ax[1].set_title("Where routing load moved"); ax[1].legend(); ax[1].grid(alpha=0.3)
    fig.suptitle("Model MRI diff — Qwen3.6-35B-A3B base vs Cyber-Tiel-Coder (same UD-Q5_K_XL quant)")
    fig.tight_layout(); out=f"{SP}/mri_diff.png"; fig.savefig(out, dpi=110, bbox_inches="tight")
    print(f"\ndiff plot -> {out}")

if __name__ == "__main__":
    main()
