#!/usr/bin/env python3
"""Score PREREG_HESITATION_KLD.md.  Runs on .194 (reads the uint16 base + dumps in place).
usage: analyze_hes.py BASE REF_GGUF DUMPDIR OUT.json
Base layout (perplexity.cpp): '_logits_' | int32 n_ctx | int32 n_vocab | int32 n_chunk | int32 tokens[n_chunk*n_ctx]
  | per chunk: n_pos rows of nv uint16, nv = 2*((n_vocab+1)//2)+4; row = float32 scale, float32 min_log_prob,
  then n_vocab uint16 q (logp = min_log_prob + scale*q; q==0 means <= the floor, 16 nats below max).
Dump layout: int32 n_pos | int32 n_chunk | float32 kld[n_chunk*n_pos].  Position i of chunk c predicts
token tokens[c*n_ctx + n_ctx//2 + i + 1]."""
import json, sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path.home() / "buun-llama-cpp/gguf-py"))
from gguf import GGUFReader

BASE, REF, DUMPDIR, OUT = sys.argv[1:5]
MARKERS = {"Wait", "But", "Hmm", "Actually", "Alternatively", "However", "Hold", "Oh", "Maybe", "Perhaps"}
ARMS = ["Q2KXL", "IQ3XXS", "IQ4XS", "Q4KM", "Q6K"]
B = 10000
rng = np.random.default_rng(0)

# --- GPT-2 byte-level decode for the vocab
def bytes_to_unicode():
    bs = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256)); cs = bs[:]; n = 0
    for b in range(256):
        if b not in bs: bs.append(b); cs.append(256 + n); n += 1
    return {chr(c): b for b, c in zip(bs, cs)}
U2B = bytes_to_unicode()
r = GGUFReader(REF)
f = r.fields["tokenizer.ggml.tokens"]
vocab = [bytes(f.parts[i]).decode("utf-8", "replace") for i in f.data]
def dec(t):
    try: return bytes(U2B[c] for c in t).decode("utf-8", "replace")
    except KeyError: return t
is_hes_tok = np.array([dec(t).strip() in MARKERS and not dec(t).strip() == "" for t in vocab])
print("marker token ids:", int(is_hes_tok.sum()), sorted({dec(vocab[i]).strip() for i in np.nonzero(is_hes_tok)[0]}))

# --- base: tokens + entropy per scored position
with open(BASE, "rb") as fh:
    assert fh.read(8) == b"_logits_"
    n_ctx, n_vocab, n_chunk = np.frombuffer(fh.read(12), dtype=np.int32)
    toks = np.frombuffer(fh.read(4 * n_chunk * n_ctx), dtype=np.int32).reshape(n_chunk, n_ctx)
    hdr = fh.tell()
nv = 2 * ((n_vocab + 1) // 2) + 4
first = n_ctx // 2; n_pos = n_ctx - 1 - first
mm = np.memmap(BASE, dtype=np.uint16, mode="r", offset=hdr, shape=(n_chunk * n_pos, nv))
H = np.empty(n_chunk * n_pos, dtype=np.float64); P1 = np.empty_like(H)
for s in range(0, len(H), 256):
    blk = np.array(mm[s:s + 256])
    fl = blk[:, :4].copy().view(np.float32)             # scale, min_log_prob
    scale, mn = fl[:, 0:1].astype(np.float64), fl[:, 1:2].astype(np.float64)
    q = blk[:, 4:4 + n_vocab].astype(np.float64)
    lp = mn + scale * q
    lp = np.where(q > 0, lp, -np.inf)                     # floor entries carry ~0 mass
    p = np.exp(lp); p /= p.sum(1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        H[s:s + len(blk)] = -np.nansum(np.where(p > 0, p * np.log(p), 0), 1)
    P1[s:s + len(blk)] = p.max(1)
nxt = toks[:, first + 1:first + 1 + n_pos].reshape(-1)
hes = is_hes_tok[nxt]
chunk_of = np.repeat(np.arange(n_chunk), n_pos)
print(f"chunks {n_chunk} scored positions {len(H)} HES positions {int(hes.sum())}")

def load_dump(a):
    b = np.fromfile(Path(DUMPDIR) / f"{a}.kld.bin", dtype=np.uint8)
    npos, nch = np.frombuffer(b[:8].tobytes(), dtype=np.int32)
    assert npos == n_pos and nch == n_chunk, (a, npos, nch)
    return np.frombuffer(b[8:].tobytes(), dtype=np.float32).astype(np.float64)

dec_edges = np.quantile(H, np.linspace(0, 1, 11)); dec_edges[-1] += 1e-9
dbin = np.clip(np.searchsorted(dec_edges, H, side="right") - 1, 0, 9)

def stats(k, idx):
    """k: per-position KLD; idx: chunk ids to include (bootstrap sample, with repetition)."""
    sel = np.concatenate([np.nonzero(chunk_of == c)[0] for c in idx]) if idx is not None else np.arange(len(k))
    kk, hh, bb = k[sel], hes[sel], dbin[sel]
    raw = kk[hh].mean() / kk[~hh].mean()
    num = den = 0.0
    for d in range(10):
        m = bb == d; nh = (m & hh).sum()
        if nh and (m & ~hh).sum():
            num += nh * kk[m & hh].mean(); den += nh * kk[m & ~hh].mean()
    return raw, (num / den if den else np.nan), kk.mean(), kk[hh].mean()

K = {a: load_dump(a) for a in ARMS}
res = {"n_chunk": int(n_chunk), "n_pos": int(n_pos), "hes_positions": int(hes.sum()),
       "entropy_mean_hes": float(H[hes].mean()), "entropy_mean_other": float(H[~hes].mean()),
       "arms": {}}
idx_boot = [rng.integers(0, n_chunk, n_chunk) for _ in range(B)]
chunk_index = [np.nonzero(chunk_of == c)[0] for c in range(n_chunk)]
def stats_fast(k, idx):
    sel = np.concatenate([chunk_index[c] for c in idx])
    kk, hh, bb = k[sel], hes[sel], dbin[sel]
    raw = kk[hh].mean() / kk[~hh].mean()
    num = den = 0.0
    for d in range(10):
        m = bb == d; mh = m & hh; nh = mh.sum(); mo = m & ~hh
        if nh and mo.sum(): num += nh * kk[mh].mean(); den += nh * kk[mo].mean()
    return raw, num / den, kk.mean(), kk[hh].mean()
boots = {}
for a in ARMS:
    pt = stats_fast(K[a], range(n_chunk))
    bs = np.array([stats_fast(K[a], ix) for ix in idx_boot])   # 10,000 resamples, as registered
    boots[a] = bs
    ci = lambda j: [float(np.nanpercentile(bs[:, j], 2.5)), float(np.nanpercentile(bs[:, j], 97.5))]
    res["arms"][a] = {"mean_kld": pt[2], "hes_kld": pt[3], "raw_ratio": pt[0], "raw_ratio_ci": ci(0),
                      "entropy_matched_ratio": pt[1], "entropy_matched_ci": ci(1),
                      "top1_agree_hes": None}
    print(f"{a:7s} meanKLD {pt[2]:.5f}  HES {pt[3]:.5f}  raw ratio {pt[0]:6.2f} {ci(0)}  entropy-matched {pt[1]:5.2f} {ci(1)}")
# H3: raw ratio Q2KXL - Q6K ; H4: separation
d3 = boots["Q2KXL"][:, 0] - boots["Q6K"][:, 0]
res["H3_diff_ci"] = [float(np.percentile(d3, 2.5)), float(np.percentile(d3, 97.5))]
res["H4_hes_sep"] = res["arms"]["Q2KXL"]["hes_kld"] / res["arms"]["Q6K"]["hes_kld"]
res["H4_mean_sep"] = res["arms"]["Q2KXL"]["mean_kld"] / res["arms"]["Q6K"]["mean_kld"]
# descriptive: per-decile curves and per-marker
res["decile_edges"] = dec_edges.tolist()
res["curves"] = {a: {"hes": [float(K[a][(dbin == d) & hes].mean()) if ((dbin == d) & hes).any() else None for d in range(10)],
                     "other": [float(K[a][(dbin == d) & ~hes].mean()) for d in range(10)],
                     "n_hes": [int(((dbin == d) & hes).sum()) for d in range(10)]} for a in ARMS}
per = {}
for tid in np.unique(nxt[hes]):
    w = dec(vocab[tid]).strip(); m = nxt == tid
    per.setdefault(w, {"n": 0})["n"] += int(m.sum())
    for a in ARMS: per[w][a] = per[w].get(a, 0) + float(K[a][m].sum())
res["per_marker"] = {w: {"n": v["n"], **{a: v[a] / v["n"] for a in ARMS}} for w, v in per.items()}
Path(OUT).write_text(json.dumps(res, indent=1))
print("H3 diff CI", res["H3_diff_ci"], " H4 hes-sep", round(res["H4_hes_sep"], 2), "mean-sep", round(res["H4_mean_sep"], 2))
print("entropy HES", round(res["entropy_mean_hes"], 3), "OTHER", round(res["entropy_mean_other"], 3))
