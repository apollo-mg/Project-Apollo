#!/usr/bin/env python3
"""Model MRI analysis: from a moe-capture trace, compute expert utilization, adjacent-token
routing locality (vs edge0's ~25% baseline), and routing entropy; draw the layer x expert grid."""
import struct, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

K = 8            # Qwen3.6-35B-A3B routing width (n_expert_used)
SP = sys.argv[1] if len(sys.argv) > 1 else "."

def load(path):
    layers = {}
    with open(path, "rb") as f:
        while True:
            h = f.read(12)
            if len(h) < 12: break
            layer, ne, nt = struct.unpack("<iii", h)
            data = np.frombuffer(f.read(4*ne*nt), dtype=np.float32).reshape(nt, ne)  # [token, expert]
            layers[layer] = data
    return layers  # {layer: probs[nt, ne]}

def analyze(layers):
    L = sorted(layers)
    ne = layers[L[0]].shape[1]
    util = np.zeros((len(L), ne))       # fraction of tokens with expert in top-K, per layer
    overlap = np.zeros(len(L))          # mean adjacent-token top-K overlap
    entropy = np.zeros(len(L))          # mean router entropy (bits)
    topmass = np.zeros(len(L))          # mean prob mass in the top-K
    for i, l in enumerate(L):
        p = layers[l]                    # [nt, ne]
        nt = p.shape[0]
        topk = np.argpartition(-p, K, axis=1)[:, :K]   # [nt, K] expert ids
        for e_row in topk:
            util[i, e_row] += 1
        util[i] /= nt
        # adjacent-token overlap of the top-K sets
        sets = [set(row.tolist()) for row in topk]
        ov = [len(sets[t] & sets[t+1]) / K for t in range(nt-1)]
        overlap[i] = np.mean(ov)
        # entropy (bits) over full router dist, mean over tokens
        pe = np.clip(p, 1e-12, 1.0)
        entropy[i] = np.mean(-(pe*np.log2(pe)).sum(axis=1))
        # top-K prob mass
        sp = np.sort(p, axis=1)[:, -K:].sum(axis=1)
        topmass[i] = np.mean(sp)
    return dict(L=L, ne=ne, util=util, overlap=overlap, entropy=entropy, topmass=topmass)

def summarize(name, a):
    dead = int((a["util"].sum(axis=0) == 0).sum())      # experts never used in any layer
    print(f"\n== {name} ==")
    print(f"  layers={len(a['L'])} experts={a['ne']}")
    print(f"  adjacent-token top-{K} overlap: mean={a['overlap'].mean():.3f}  "
          f"(edge0 general baseline ~0.25)  range[{a['overlap'].min():.2f},{a['overlap'].max():.2f}]")
    print(f"  router entropy (bits):  mean={a['entropy'].mean():.2f}  (log2(256)=8.0 = uniform)")
    print(f"  top-{K} prob mass:      mean={a['topmass'].mean():.3f}")
    print(f"  experts never selected (any layer): {dead}/{a['ne']}")
    # most and least local layers
    order = np.argsort(a['overlap'])
    print(f"  most local layers (overlap): " + ", ".join(f"L{a['L'][j]}={a['overlap'][j]:.2f}" for j in order[::-1][:3]))
    print(f"  least local layers:          " + ", ".join(f"L{a['L'][j]}={a['overlap'][j]:.2f}" for j in order[:3]))

def main():
    code = analyze(load(f"{SP}/mri_code.bin"))
    prose = analyze(load(f"{SP}/mri_prose.bin"))
    summarize("CODE (Cyber-Tiel-35B-A3B)", code)
    summarize("PROSE (Cyber-Tiel-35B-A3B)", prose)
    print(f"\n== code vs prose ==")
    print(f"  overlap: code {code['overlap'].mean():.3f}  vs prose {prose['overlap'].mean():.3f}  "
          f"(delta {code['overlap'].mean()-prose['overlap'].mean():+.3f})")
    print(f"  entropy: code {code['entropy'].mean():.2f}  vs prose {prose['entropy'].mean():.2f} bits")

    # ---- the grid ----
    fig, ax = plt.subplots(1, 3, figsize=(16, 6), gridspec_kw={"width_ratios":[5,5,3]})
    for k, (name, a) in enumerate([("code", code), ("prose", prose)]):
        im = ax[k].imshow(a["util"], aspect="auto", cmap="magma", vmin=0, vmax=a["util"].max(),
                          interpolation="nearest")
        ax[k].set_title(f"Cyber-Tiel-35B-A3B  expert utilization ({name})", fontsize=11)
        ax[k].set_xlabel("expert (0-255)"); ax[k].set_ylabel("layer")
        fig.colorbar(im, ax=ax[k], fraction=0.046, label="frac tokens in top-8")
    ax[2].plot(code["overlap"], code["L"], label="code", color="#e6550d")
    ax[2].plot(prose["overlap"], prose["L"], label="prose", color="#3182bd")
    ax[2].axvline(0.25, ls="--", color="gray", label="edge0 ~0.25")
    ax[2].invert_yaxis(); ax[2].set_xlabel("adj-token top-8 overlap"); ax[2].set_ylabel("layer")
    ax[2].set_title("routing locality by layer"); ax[2].legend(fontsize=8); ax[2].grid(alpha=0.3)
    fig.suptitle("Model MRI — MoE expert routing (Cyber-Tiel-Coder-35B-A3B)", fontsize=13)
    fig.tight_layout()
    out = f"{SP}/mri_heatmap.png"
    fig.savefig(out, dpi=110, bbox_inches="tight")
    print(f"\nheatmap -> {out}")

if __name__ == "__main__":
    main()
